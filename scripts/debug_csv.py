# -*- coding: utf-8 -*-
import csv
import io

text = ('\ufeffphone,name,estate,layout,area,budget_range,style,intent_time,channel,tags,source\r\n'
        '13500000001,CSV甲,卓越中环,四房,140,50-80万,现代简约,1个月内,抖音,改善,批量\r\n'
        '13500000002,CSV乙,保利和光尘樾,,,,,2个月内,小红书,,批量\r\n'
        '13500000001,CSV甲改,,,,,,,,,,\r\n'
        ',,缺号行,,,,,,,,\r\n'
        '\r\n')
text = text.lstrip("\ufeff")
reader = csv.DictReader(io.StringIO(text))
print("fieldnames:", reader.fieldnames)
for i, rec in enumerate(reader, 1):
    print(i, rec)
    for k, v in rec.items():
        if not isinstance(v, str):
            print("  非字符串:", repr(k), repr(v), type(v))
