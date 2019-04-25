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
#  - os needed for file and directory manipulation
#  - re regexp module for string manipulation.
import os
import re

# Import 3th party modules:
#  - wexpect to launch ant interact with subprocesses.
#  - logging to write logs of running
import logging
import wexpect

cleyeLogo = '''
       _                      
      | |                     
   ___| | ___ _   _  ___      
  / __| |/ _ \ | | |/ _ \     
 | (__| |  __/ |_| |  __/     
  \___|_|\___|\__, |\___|     
               __/ |          
              |___/                             
'''


# Path of Vivado executable:
vivadoPath = 'C:/Xilinx/Vivado/2017.4/bin/vivado.bat'
vivadoArgs = ['-mode', 'tcl']
vivadoPrompt = 'Vivado% '

# Setup logging 
logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename='cleye.log', filemode='w', format='%(asctime)s - %(name)s: [%(levelname)s] %(message)s')


def do(proc, cmd, prompt = vivadoPrompt, puts = False):
    proc.sendline(cmd)
    if prompt:
        proc.expect(vivadoPrompt)
        logging.debug(cmd + proc.before + proc.match.group(0))
        if puts:
            print(cmd, end='')
            print(proc.before, end='')
            print(proc.match.group(0), end='')
        
        
def chooseDevice(proc, devices, side, vivadoPrompt=vivadoPrompt, puts=False):
    # Print devices to user to choose from them.
    for i, dev in enumerate(devices):
        print(str(i) + ' ' + dev)

    print('Print choose an {} device: '.format(side), end='')
    deviceId = input()
    device = devices[deviceId]

    do(proc, 'set_device ' + device, vivadoPrompt, puts)


def chooseSio(proc, side, vivadoPrompt=vivadoPrompt, puts=False):
    do(proc, '', vivadoPrompt, puts)
    do(proc, 'get_hw_sio_gts', vivadoPrompt, puts)
    sios = [x for x in proc.before.splitlines() if x ]
    sios = sios[0].split(' ')
    for i, sio in enumerate(sios):
        print(str(i) + ' ' + sio)
    print('Print choose a SIO for {} side : '.format(side), end='')
    sioId = input()
    sio = sios[sioId]

    do(proc, 'create_link ' + sio, vivadoPrompt, puts)
    
    
def get_property(proc, propName, objectName, vivadoPrompt=vivadoPrompt, puts=True):
    cmd = 'get_property {} {}'.format(propName, objectName)
    do(proc, cmd, vivadoPrompt, puts)
    val = [x for x in proc.before.splitlines() if x ]
    return val[0]
    
    
def set_property(proc, propName, value, objectName, vivadoPrompt=vivadoPrompt, puts=True):
    cmd = 'set_property {} {} {}'.format(propName, value, objectName)
    do(proc, cmd, vivadoPrompt, puts)
    
    
def independent_finder(vivadoTX, vivadoRx):
    TXDIFFSWING_values = [
        "{269 mV (0000)}" ,
        "{336 mV (0001)}" ,
        # "{407 mV (0010)}" ,
        # "{474 mV (0011)}" ,
        # "{543 mV (0100)}" ,
        # "{609 mV (0101)}" ,
        # "{677 mV (0110)}" ,
        # "{741 mV (0111)}" ,
        # "{807 mV (1000)}" ,
        # "{866 mV (1001)}" ,
        # "{924 mV (1010)}" ,
        # "{973 mV (1011)}" ,
        # "{1018 mV (1100)}",
        # "{1056 mV (1101)}",
        # "{1092 mV (1110)}",
        # "{1119 mV (1111)}"
    ]
    
    globalIteration = 1
    globalParameterSpace = {}
    globalParameterSpace["TXDIFFSWING"] = TXDIFFSWING_values

    if not os.path.exists("runs"):
        os.makedirs("runs")

    for i in range(globalIteration):
        for pName, pValues in globalParameterSpace.items():
            openAreas = []
            maxArea   = 0
            bestValue = get_property(vivadoTX, pName, '[get_hw_sio_links]')
            
            for pValue in pValues:
                print("Create scan ({} {})".format(pName, pValue))
                set_property(vivadoTX, pName, pValue, '[get_hw_sio_links]')
                do(vivadoTX, 'commit_hw_sio [get_hw_sio_links]')
                
                checkValue = get_property(vivadoTX, pName, '[get_hw_sio_links]')
                if checkValue not in pValue: # Readback does not contains brackets {}
                    print("ERROR: Something went wrong. Cannot set value {}  {} ".format(checkValue, pValue))

                fname = "{}{}{}".format(i, pName, pValue)
                fname = re.sub('\\W', '_', fname)
                fname = "runs/" + fname + '.csv'
                
                cmd = 'set openArea [run_scan [get_hw_sio_links] "{}"]'.format(fname)
                do(vivadoRx, cmd)
                do(vivadoRx, 'puts $openArea')
                openArea = [x for x in vivadoRx.before.splitlines() if x ]
                openArea = openArea[0]
                print('OpenArea: {}'.format(openArea))
                openAreas.append(openArea)
                
                if openArea > maxArea:
                    maxArea = openArea
                    bestValue = pValue
                
            print("pName:  {}    bestParam:  {}".format(pName, bestValue))
            
            set_property(vivadoTX, pName, bestValue, '[get_hw_sio_links]')
            do(vivadoTX, 'commit_hw_sio [get_hw_sio_links]')


print(cleyeLogo)
       
logging.info('Spawning Vivado instances (TX/RX)')
vivadoTX = wexpect.spawn(vivadoPath, vivadoArgs)
vivadoRX = wexpect.spawn(vivadoPath, vivadoArgs)

logging.info('Warning for prompt of Vivado (waiting for Vivado startup)')
vivadoTX.expect(vivadoPrompt)
vivadoRX.expect(vivadoPrompt)

# print the texts
print(vivadoTX.before, end='')
print(vivadoTX.match.group(0), end='')


do(vivadoRX, 'source sourceme.tcl')
do(vivadoTX, 'source sourceme.tcl')
do(vivadoRX, 'set devices [fetch_devices]')
do(vivadoRX, 'puts $devices')
# devices = vivadoRX.before

# Get a list of all devices on all target.
# Remove empty lines (first line will be empty)
# And remove the brackets. fetch_devices returns lists.
devices = [x[1:-1] for x in vivadoRX.before.splitlines() if x ]

#
# Choose TX/RX device
# 
chooseDevice(vivadoTX, devices, 'TX')
chooseDevice(vivadoRX, devices, 'RX')

#
# Choose SIOs
# 
chooseSio(vivadoTX, 'TX')
chooseSio(vivadoRX, 'RX')

independent_finder(vivadoTX, vivadoRX)

print('')
print('All Script has been run.')
print('Switch to RX vivado console:')
print('')
do(vivadoRX, '', vivadoPrompt, True)

vivado = vivadoRX

while True:
    cmd = raw_input()
    if cmd.startswith('!'):
        # Cleye command
        cmd = cmd[1:].lower()
        if cmd == 'rx':
            print('Switching to VivadoRX')
            vivado = vivadoRX
            do(vivado, '', vivadoPrompt, True)
        elif cmd == 'tx':
            print('Switching to VivadoTX')
            vivado = vivadoTX
            do(vivado, '', vivadoPrompt, True)
        elif cmd in ['q', 'quit', 'exit']:
            print('Exiting to VivadoTX')
            do(vivadoTX, 'exit', vivadoPrompt, True)
            vivadoTX.wait()
            print('Exiting to VivadoRX')
            do(vivadoRX, 'exit', vivadoPrompt, True)
            vivadoRX.wait()
            break
    else:
        # Vivado command
        do(vivado, cmd, vivadoPrompt, True)
    
    
    
