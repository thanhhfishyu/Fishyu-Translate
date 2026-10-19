import sys

ver = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
parts = [int(x) for x in ver.split(".")] + [0] * 4
with open("fishyu/_version.py", "w", encoding="utf-8") as f:
    f.write(f'VERSION = "{ver}"\n')
tup = tuple(parts[:4])
with open("version_info.txt", "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'thanhhfishyu'),
      StringStruct('FileDescription', 'Fishyu Translate for Windows'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'FishyuTranslate'),
      StringStruct('OriginalFilename', 'FishyuTranslate.exe'),
      StringStruct('ProductName', 'Fishyu Translate for Windows'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")
print(ver)
