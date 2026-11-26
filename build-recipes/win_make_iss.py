# Create inno setup .iss file
import os.path as op
import platform
import sys

import chipstream

# make library available
cdir = op.dirname(op.abspath(__file__))
pdir = op.dirname(cdir)
sys.path.insert(0, pdir)

# get version
version = chipstream.__version__

# read dummy
with open(op.join(cdir, "win_chipstream.iss_dummy"), 'r') as dummy:
    iss = dummy.readlines()

# replace keywords
for i in range(len(iss)):
    if iss[i].strip().startswith("#define MyAppVersion"):
        iss[i] = f'#define MyAppVersion "{version:s}"\n'
    if iss[i].strip().startswith("#define MyAppPlatform"):
        # sys.maxint returns the same for windows 64bit verions
        iss[i] = f'#define MyAppPlatform "win_{platform.architecture()[0]}"\n'

# write iss
with open(op.join(cdir, "win_chipstream.iss"), 'w') as issfile:
    issfile.writelines(iss)
