#include <QCoreApplication>
#include <QVector>
#include <QString>
#include <QList>
#include <QPointer>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonValue>
#include <QJsonDocument>

int main(int argc, char *argv[])
{
   QCoreApplication a(argc, argv);

   QString s = "Hello World";

   QVector<int> vi;
   vi << 11;
   vi << 22;
   vi << 33;

   QVector<QString> vs;
   vs << "Hello";
   vs << "World";

   QVector<QVector<QString>> vvs;
   vvs << vs;
   vvs << vs;

   QList<int> li;
   li << 11;
   li << 22;
   li << 33;

   QList<QString> ls;
   ls << "Hello";
   ls << "World";

   QList<QList<QString>> lls;
   lls << ls;
   lls << ls;

   QPointer<QCoreApplication> ap;
   ap = &a;

   QJsonObject jo;
   jo["name"] = "Qt";
   jo["version"] = 5;
   jo["awesome"] = true;

   QJsonArray ja;
   ja.append(1);
   ja.append("two");
   ja.append(false);

   QJsonValue jv = jo["name"];

   QJsonDocument jd(jo);


   return a.exec();
}
