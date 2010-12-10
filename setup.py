import os
import py2exe
import sys
from distutils.core import setup

MANIFEST = '''
<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
manifestVersion="1.0">
  <assemblyIdentity
    version="2.0.0.0"
    processorArchitecture="x86"
    name="Star Rocket Level Editor"
    type="win32"
  />
  <description>Star Rocket Level Editor 1.0</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
          level="asInvoker"
          uiAccess="false"
        />
      </requestedPrivileges>
    </security>
  </trustInfo>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
        type="win32"
        name="Microsoft.VC90.CRT"
        version="9.0.21022.8"
        processorArchitecture="x86"
        publicKeyToken="1fc8b3b9a1e18e3b"
      />
    </dependentAssembly>
  </dependency>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
        type="win32"
        name="Microsoft.Windows.Common-Controls"
        version="6.0.0.0"
        processorArchitecture="x86"
        publicKeyToken="6595b64144ccf1df"
        language="*"
      />
    </dependentAssembly>
  </dependency>
</assembly>
'''

# Don't require the command line argument.
sys.argv.append('py2exe')

# Build the distribution.
setup(
    options = {"py2exe":{
        "compressed": True,
        "optimize": 2,
        "bundle_files": 1,
        #"includes": ['encodings', 'encodings.cp437'],
        "excludes": ['Tkconstants', 'Tkinter', 'tcl'],
        "dll_excludes": ['msvcp90.dll'],
    }},
    windows = [{
        "script": "main.py",
        "dest_base": "star-edit",
        "icon_resources": [(1, "images/icon.ico")],
        "other_resources": [(24, 1, MANIFEST)],
    }],
    data_files = [
        ('Microsoft.VC90.CRT', [
            'Microsoft.VC90.CRT/Microsoft.VC90.CRT.manifest',
            'Microsoft.VC90.CRT/msvcm90.dll',
            'Microsoft.VC90.CRT/msvcp90.dll',
            'Microsoft.VC90.CRT/msvcr90.dll',
        ])
    ],
)
