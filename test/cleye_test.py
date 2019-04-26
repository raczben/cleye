# This file is part of cleye.
# 
#     Cleye is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     Foobar is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
# 
#     You should have received a copy of the GNU General Public License
#     along with Foobar.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import print_function

# Import build in modules
#  - sys manipulate python path
#  - os needed for file and directory manipulation
import sys
import os

# To import cleye we must add to path
test_path = os.path.dirname(os.path.abspath(__file__))
cleye_module_path = os.path.join(test_path, '..')
sys.path.insert(0, cleye_module_path) 

# Import the DUT
import cleye

# test scan csv files (under resources dir)
names = [
    'non_valid_eye_bath_tub_sweep_01', 
    'non_valid_eye_sweep_01',
    'non_valid_eye_sweep_02',
    'non_valid_eye_sweep_03',
    'valid_eye_bathtub_sweep_01',
    'valid_eye_bathtub_sweep_02',
    'valid_eye_but_closed_sweep_01',
    'valid_eye_but_closed_sweep_02',
    'valid_eye_but_closed_sweep_03',
    ]
    
scanStructures = {}
print('Start parsing csv files...', end='')
for name in names:
    filename = os.path.join(test_path, 'resources', name + '.csv')
    scanStructures[name] = cleye.readCsv(filename)
    
print(' [  OK  ]')


print('Testnig valid eye...', end='')
ok = True
for name, scanStruct in scanStructures.items():
    validEye = cleye._testEye(scanStruct['scanData'])
    if 'non_valid' in name:
        validEyeExpected = False
    else:
        validEyeExpected = True
    if validEye != validEyeExpected:
        print('Error: Mismatch: validEye != validEyeExpected ' + name)
        ok = False

if ok:
    print(' [  OK  ]')


print('Testnig open areas...')
ok = True
for name, scanStruct in scanStructures.items():
    openArea = cleye.getOpenArea(scanStruct)
    if 'non_valid' in name:
        assert(openArea==0.0)
    else:
        assert(openArea>0.0)
    print(name + ': ' + str(openArea))
print(' [  OK  ]')


