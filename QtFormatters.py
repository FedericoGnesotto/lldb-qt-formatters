import lldb
from builtins import chr

def QUrl_SummaryProvider(valobj, internal_dict):
   return valobj.GetFrame().EvaluateExpression(valobj.GetName() + '.toString((QUrl::FormattingOptions)QUrl::PrettyDecoded)');

# Serialising Qt JSON types from lldb is awkward: most QString/QByteArray helpers
# (fromUtf8(QByteArray), constData(), ...) are inline in Qt and therefore have no
# callable symbol in the target. What *does* work reliably is QJsonDocument::toJson(),
# which is an exported function returning a QByteArray by value. So we evaluate that,
# then read the resulting QByteArray's bytes straight out of target memory instead of
# making further (impossible) inline calls.
#
# lldb also frequently can't resolve the bare unscoped enumerator QJsonDocument::Compact,
# so we prefer the enum-name-qualified spelling and fall back to the raw integer value.
_QJSON_FORMAT_FORMS = ['QJsonDocument::JsonFormat::Compact', 'QJsonDocument::Compact', '(QJsonDocument::JsonFormat)1']

def _read_qbytearray(value):
   if value is None or not value.IsValid():
       return None
   d = value.GetChildMemberWithName('d')
   if not d.IsValid():
       return None
   process = value.GetProcess()
   err = lldb.SBError()
   size = d.GetChildMemberWithName('size').GetValueAsUnsigned()
   if size == 0:
       return ''
   # Qt 6: d is a QArrayDataPointer<char> holding an explicit data pointer 'ptr'.
   ptr = d.GetChildMemberWithName('ptr')
   if ptr.IsValid() and ptr.GetValueAsUnsigned() != 0:
       addr = ptr.GetValueAsUnsigned()
   else:
       # Qt 5: d is a QByteArrayData*; the bytes live at reinterpret_cast<char*>(d) + offset.
       offset = d.GetChildMemberWithName('offset')
       if not offset.IsValid():
           return None
       addr = d.GetValueAsUnsigned() + offset.GetValueAsUnsigned()
   mem = process.ReadMemory(addr, size, err)
   if not err.Success() or mem is None:
       return None
   return mem.decode('utf-8', 'replace')

def _eval_qjson(valobj, templates, strip_brackets=False):
   # Each template is an expression yielding a QByteArray, with __FMT__ standing in
   # for the toJson() format argument. (A sentinel is used instead of str.format so
   # literal { } braces in the expression don't need escaping.) The templates are
   # tried in order, and for each we try the format spellings until one compiles.
   if isinstance(templates, str):
       templates = [templates]
   frame = valobj.GetFrame()
   for tmpl in templates:
       for fmt in _QJSON_FORMAT_FORMS:
           result = frame.EvaluateExpression(tmpl.replace('__FMT__', fmt))
           if result is None or not result.GetError().Success():
               continue
           text = _read_qbytearray(result)
           if text is None:
               continue
           if strip_brackets:
               # The value was wrapped in a single-element array; drop the [ ] (and
               # any surrounding whitespace) to leave just the serialised value.
               text = text.strip()
               if text.startswith('[') and text.endswith(']'):
                   text = text[1:-1].strip()
           return text
   return None

def QJsonObject_SummaryProvider(valobj, internal_dict):
   return _eval_qjson(valobj, 'QJsonDocument(' + valobj.GetName() + ').toJson(__FMT__)')

def QJsonArray_SummaryProvider(valobj, internal_dict):
   return _eval_qjson(valobj, 'QJsonDocument(' + valobj.GetName() + ').toJson(__FMT__)')

def QJsonDocument_SummaryProvider(valobj, internal_dict):
   return _eval_qjson(valobj, valobj.GetName() + '.toJson(__FMT__)')

_qjson_value_counter = [0]

def QJsonValue_SummaryProvider(valobj, internal_dict):
   # There is no direct toJson() for a single value, so wrap it in a one-element
   # array, serialise that, and strip the surrounding [ ]. The statement form uses
   # a per-call unique name because lldb persists expression locals across
   # evaluations, so a fixed name would clash on the second run. append() is
   # preferred because it is an out-of-line symbol, whereas the initializer_list
   # constructor (kept as a fallback) is usually not synthesisable by lldb.
   name = valobj.GetName()
   _qjson_value_counter[0] += 1
   var = '__qt_jv_%d' % _qjson_value_counter[0]
   templates = [
       'QJsonArray ' + var + '; ' + var + '.append(' + name + '); QJsonDocument(' + var + ').toJson(__FMT__)',
       'QJsonDocument(QJsonArray({' + name + '})).toJson(__FMT__)',
   ]
   return _eval_qjson(valobj, templates, strip_brackets=True)

def QString_SummaryProvider(valobj, internal_dict):
   def make_string_from_pointer_with_offset(F,OFFS,L):
       strval = 'u"'
       try:
           data_array = F.GetPointeeData(0, L).uint16
           for X in range(OFFS, L):
               V = data_array[X]
               if V == 0:
                   break
               strval += chr(V)
       except:
           pass
       strval = strval + '"'
       return strval

   #qt5
   def qstring_summary(value):
       try:
           d = value.GetChildMemberWithName('d')
           #have to divide by 2 (size of unsigned short = 2)
           offset = d.GetChildMemberWithName('offset').GetValueAsUnsigned() // 2
           size = get_max_size(value)
           return make_string_from_pointer_with_offset(d, offset, size)
       except:
           return value

   def get_max_size(value):
       _max_size_ = None
       try:
           debugger = value.GetTarget().GetDebugger()
           _max_size_ = int(lldb.SBDebugger.GetInternalVariableValue('target.max-string-summary-length', debugger.GetInstanceName()).GetStringAtIndex(0))
       except:
           _max_size_ = 512
       return _max_size_
   return qstring_summary(valobj)

class QVector_SyntheticProvider:
    def __init__(self, valobj, internal_dict):
            self.valobj = valobj

    def num_children(self):
            try:
                    s = self.valobj.GetChildMemberWithName('d').GetChildMemberWithName('size').GetValueAsUnsigned()
                    return s
            except:
                    return 0

    def get_child_index(self,name):
            try:
                    return int(name.lstrip('[').rstrip(']'))
            except:
                    return None

    def get_child_at_index(self,index):
            if index < 0:
                    return None
            if index >= self.num_children():
                    return None
            if self.valobj.IsValid() == False:
                    return None
            try:
                    doffset = self.valobj.GetChildMemberWithName('d').GetChildMemberWithName('offset').GetValueAsUnsigned()
                    type = self.valobj.GetType().GetTemplateArgumentType(0)
                    elementSize = type.GetByteSize()
                    return self.valobj.GetChildMemberWithName('d').CreateChildAtOffset('[' + str(index) + ']', doffset + index * elementSize, type)
            except:
                    return None

class QList_SyntheticProvider:
    def __init__(self, valobj, internal_dict):
            self.valobj = valobj

    def num_children(self):
            try:
                    listDataD = self.valobj.GetChildMemberWithName('p').GetChildMemberWithName('d')
                    begin = listDataD.GetChildMemberWithName('begin').GetValueAsUnsigned()
                    end = listDataD.GetChildMemberWithName('end').GetValueAsUnsigned()
                    return (end - begin)
            except:
                    return 0

    def get_child_index(self,name):
            try:
                    return int(name.lstrip('[').rstrip(']'))
            except:
                    return None

    def get_child_at_index(self,index):
            if index < 0:
                    return None
            if index >= self.num_children():
                    return None
            if self.valobj.IsValid() == False:
                    return None
            try:
                    pD = self.valobj.GetChildMemberWithName('p').GetChildMemberWithName('d');
                    pBegin = pD.GetChildMemberWithName('begin').GetValueAsUnsigned()
                    pArray = pD.GetChildMemberWithName('array').GetValueAsUnsigned()
                    pAt = pArray + pBegin + index
                    type = self.valobj.GetType().GetTemplateArgumentType(0)
                    elementSize = type.GetByteSize()
                    voidSize = pD.GetChildMemberWithName('array').GetType().GetByteSize()
                    return self.valobj.GetChildMemberWithName('p').GetChildMemberWithName('d').GetChildMemberWithName('array').CreateChildAtOffset('[' + str(index) + ']', pBegin + index * voidSize, type)
            except:
                    print("boned getchild")
                    return None

class QPointer_SyntheticProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        try:
            wp = self.valobj.GetChildMemberWithName('wp')
            d = wp.GetChildMemberWithName('d')
            if d.GetValueAsUnsigned() == 0 or d.GetChildMemberWithName('strongref').GetChildMemberWithName('_q_value').GetValueAsUnsigned() == 0 or wp.GetChildMemberWithName('value').GetValueAsUnsigned() == 0:
                return 0
            else:
                return 1
        except:
            return 0

    def get_child_index(self,name):
        return 0

    def get_child_at_index(self,index):
        if index < 0:
            return None
        if index >= self.num_children():
            return None
        if self.valobj.IsValid() == False:
            return None
        try:
            type = self.valobj.GetType().GetTemplateArgumentType(0)
            return self.valobj.GetChildMemberWithName('wp').GetChildMemberWithName('value').CreateChildAtOffset('value', 0, type)
        except:
            print("boned getchild")
            return None

