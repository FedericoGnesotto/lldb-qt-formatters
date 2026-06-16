# README #

I use Xcode and LLDB to debug my Qt programs, and got tired with there being no visualisation for all the built-in types. Here I endeavour to make all of these types visible through the debugger. Works with Qt 5.x.

# Supported types #

- `QString`, `QUrl`
- `QVector`, `QList` (synthetic children)
- `QPointer`
- `QJsonObject`, `QJsonArray`, `QJsonValue`, `QJsonDocument` (shown as compact JSON)

The `QJson*` summaries call `QJsonDocument::toJson()` in the inferior, so they require a live, stopped process. They have been verified against Qt 5.15.

# Installation #

Clone this repo somewhere, e.g. ~/qtlldb. Then add the following lines to your ~/.lldbinit:

```
command script import ~/qtlldb/QtFormatters.py
command source ~/qtlldb/QtFormatters.lldb
```
