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
#  - csv The Xilinx eye-scanner stores the result in csv format.
#  - argparse needed to parse command line arguments
#  - traceback handle exceptions
import os
import re
import csv
import argparse
import traceback

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


class Vivado():
    def __init__(self, executable, args):
        self.childProc = None
        self.childProc = wexpect.spawn(executable, args)
        
        
    def waitStartup(self):
        self.childProc.expect(vivadoPrompt)
        # print the texts
        print(self.childProc.before + self.childProc.match.group(0), end='')
        
        
    def do(self, cmd, prompt=vivadoPrompt, puts=False, errmsgs=[]):
        ''' do a simple command in Vivado console
        '''
        if self.childProc.terminated:
            logging.error('The process has been terminated. Sending command is not possible.')
            raise Exception('The process has been terminated. Sending command is not possible.')
        self.childProc.sendline(cmd)
        if prompt:
            self.childProc.expect(vivadoPrompt)
            logging.debug(cmd + self.childProc.before + self.childProc.match.group(0))
            for em in  errmsgs:
                if em in self.childProc.before:
                    logging.error('during running command: ' + cmd + self.childProc.before)
                    raise Exception('during running command: ' + cmd + self.childProc.before)
            if puts:
                print(cmd, end='')
                print(self.childProc.before, end='')
                print(self.childProc.match.group(0), end='')
        
        
    def chooseDevice(self, devices, side, vivadoPrompt=vivadoPrompt, puts=False):
        ''' set the hw target (blaster) and device (FPGA) for TX and RX side.
        '''
        # Print devices to user to choose from them.
        for i, dev in enumerate(devices):
            print(str(i) + ' ' + dev)

        print('Print choose an {} device: '.format(side), end='')
        deviceId = input()
        device = devices[deviceId]

        errmsgs = ['DONE status = 0', 'The debug hub core was not detected.']
        self.do('set_device ' + device, vivadoPrompt, puts, errmsgs = errmsgs)


    def chooseSio(self, side, createLink=True, vivadoPrompt=vivadoPrompt, puts=False):
        ''' Set the transceiver channel for TX/RX side.
        '''
        self.do('', vivadoPrompt, puts)
        self.do('get_hw_sio_gts', vivadoPrompt, puts)
        sios = [x for x in self.childProc.before.splitlines() if x ]
        sios = sios[0].split(' ')
        for i, sio in enumerate(sios):
            print(str(i) + ' ' + sio)
        print('Print choose a SIO for {} side : '.format(side), end='')
        sioId = input()
        sio = sios[sioId]

        if createLink:
            self.do('create_link ' + sio, vivadoPrompt, puts)
            
        return sio
        
        
    def get_var(self, varname):
        self.do('puts $' + varname)
        ret = self.childProc.before.splitlines()
        
        # remove first line, which is always empty
        ret = ret[1:] 
        # print('>>{}<<'.format(ret))
        
        # raise exception if the variable is not exist.
        if ret[0] == 'can\'t read "{}": no such variable'.format(varname):
            raise Exception(ret[0])
        
        return ret

    
    def get_property(self, propName, objectName, vivadoPrompt=vivadoPrompt, puts=True):
        ''' does a get_property command in vivado terminal. 
        
        It fetches the given property and returns it.
        '''
        cmd = 'get_property {} {}'.format(propName, objectName)
        self.do(cmd, vivadoPrompt, puts)
        val = [x for x in self.childProc.before.splitlines() if x ]
        return val[0]
    
    
    def set_property(self, propName, value, objectName, vivadoPrompt=vivadoPrompt, puts=True):
        ''' Sets a property.
        '''
        cmd = 'set_property {} {} {}'.format(propName, value, objectName)
        self.do(cmd, vivadoPrompt, puts)
        
        
    def exit(self):
        if self.childProc.terminated:
            logging.warning('This process has been terminated.')
            return None
        else:
            self.do('exit', None)
            return self.childProc.wait()
        
def _parsescanRows(scanRows):
    scanData = {
        'scanType': scanRows[0][0],
        'x':[],
        'y':[],
        'values':[]
        }
        
    if scanData['scanType'] not in ['1d bathtub', '2d statistical']:
        logging.error('Uknnown scan type: ' + scanData['scanType'])
        raise Exception('Uknnown scan type: ' + scanData['scanType'])
        
    xdata = scanRows[0][1:]
    # Need to normalize, dont know why...
    divider = abs(float(xdata[0])*2)
    
    scanData['x'] = [float(x)/divider for x in scanRows[0][1:]]
    
    for r in scanRows[1:]:
        intr = [float(x) for x in r]
        scanData['y'].append(intr[0])
        scanData['values'].append(intr[1:])
       
    return scanData

    
def readCsv(filename):
    ret = {}
    scanRows = []
    storeScanRows = False
    
    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if row[0] == 'Scan Start':
                storeScanRows = True
                continue
            elif row[0] == 'Scan End':
                storeScanRows = False
                ret['scanData'] = _parsescanRows(scanRows)
                continue
            elif storeScanRows:
                scanRows.append(row)
                continue
            else:
                # Try to convert numbers if ots possible
                try:
                    val = float(row[1])
                except ValueError:
                    val = row[1]
                ret[row[0]] = val
    return ret
    

def _testEye(scanData, xLimit = 0.45, xValLimit = 0.005):
    ''' Test that the read data is an eye or not.
    A valid eye must contains 'bit errors' at the edges. If the eye is clean at +-0.500 UI, this
    definetly not an eye.
    '''
    
    # print('x: ' + str(scanData['x']))
    # print('y: ' + str(scanData['y']))
    # print('values: ' + str(scanData['values']))
    
    # Get the indexes of the 'edge'
    # Edge means where abs(x) offset is big, bigger than 0.45.
    edgeIndexes=[i for i,x in enumerate(scanData['x']) if abs(x) > xLimit]
    if len(edgeIndexes) < 2:
        logging.warning('Too few edge indexes')
        return False
        
    # print('edgeIndexes: ' + str(edgeIndexes))
    
    # edgeValues contains BER values of the edge positions.
    edgeValues = []
    for v in scanData['values']:
        edgeValues.append([v[i] for i in edgeIndexes])
    
    # print('edgeValues: ' + str(edgeValues))
    # A valid eye must contains high BER values at the edges:
    globalMinimum = min([min(ev) for ev in edgeValues])
    
    if globalMinimum < xValLimit:
        logging.info('globalMinimum ({}) is less than xValLimit ({})  -> NOT a valid eye.'.format(globalMinimum, xValLimit))
        return False
    else:
        logging.debug('globalMinimum ({}) is greater than xValLimit ({})  -> Valid eye.'.format(globalMinimum, xValLimit))
        return True


def _getArea(scanData, xLimit = 0.2):
    ''' This is an improoved area meter. 
    Returns the open area of an eye even if there is no definite open eye.
    Returns the center area multiplied by the BER values. (ie the average of the center area.)
    '''
    
    # Get the indexes of the 'center'
    # Center means where abs(x) offset is small, less than 0.1.
    centerIndexes=[i for i,x in enumerate(scanData['x']) if abs(x) < xLimit]
    if len(centerIndexes) < 2:
        logging.warning('Too few center indexes')
        return False
    
    # centerValues contains BER values of the center positions.
    centerValues = []
    for v in scanData['values']:
        centerValues.append([v[i] for i in centerIndexes])
    
    # Get the avg center value:
    centerAvg = [float(sum(cv))/float(len(cv)) for cv in centerValues]
    centerAvg = float(sum(centerAvg))/float(len(centerAvg))
    
    return centerAvg
        
def getOpenArea(scanStructure):
    if _testEye(scanStructure['scanData']):
        if scanStructure['Open Area'] < 1.0:
            # if the 'offitial open area' is 0 try to improove:
            return _getArea(scanStructure['scanData'])
        else:
            return scanStructure['Open Area']
    else:
        return 0.0
    
    
def independent_finder(vivadoTX, vivadoRX, txSio):
    ''' Runs the optimizer algorithm.
    '''
    TXDIFFSWING_values = [
        "{269 mV (0000)}" ,
        # "{336 mV (0001)}" ,
        # "{407 mV (0010)}" ,
        # "{474 mV (0011)}" ,
        # "{543 mV (0100)}" ,
        # "{609 mV (0101)}" ,
        "{677 mV (0110)}" ,
        # "{741 mV (0111)}" ,
        # "{807 mV (1000)}" ,
        # "{866 mV (1001)}" ,
        "{924 mV (1010)}" ,
        # "{973 mV (1011)}" ,
        "{1018 mV (1100)}",
        # "{1056 mV (1101)}",
        # "{1092 mV (1110)}",
        "{1119 mV (1111)}"
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
            txSioGt = '[get_hw_sio_gts {}]'.format(txSio)
            bestValue = vivadoTX.get_property(pName, txSioGt)
            
            for pValue in pValues:
                print("Create scan ({} {})".format(pName, pValue))
                vivadoTX.set_property(pName, pValue, txSioGt)
                vivadoTX.do('commit_hw_sio ' + txSioGt)
                
                checkValue = vivadoTX.get_property(pName, txSioGt)
                if checkValue not in pValue: # Readback does not contains brackets {}
                    print("ERROR: Something went wrong. Cannot set value {}  {} ".format(checkValue, pValue))
                    
                # set_property PORT.GTRXRESET 0 [get_hw_sio_gts  {localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y0}]
                # commit_hw_sio  [get_hw_sio_gts  {localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y0}]


                fname = "{}{}{}".format(i, pName, pValue)
                fname = re.sub('\\W', '_', fname)
                fname = "runs/" + fname + '.csv'
                
                cmd = 'run_scan [get_hw_sio_links] "{}"'.format(fname)
                vivadoRX.do(cmd)
                
                scanStructure = readCsv(fname)
                openArea = getOpenArea(scanStructure)
                if openArea is None:
                    logging.error('openArea is None after reading file: ' + fname)
                            
                print('OpenArea: {}'.format(openArea))
                openAreas.append(openArea)
                
                if openArea > maxArea:
                    maxArea = openArea
                    bestValue = pValue
                
            print("pName:  {}    bestParam:  {}".format(pName, bestValue))
            
            vivadoTX.set_property(pName, bestValue, txSioGt)
            vivadoTX.do('commit_hw_sio ' + txSioGt)


def interactiveVivadoConsole(vivadoTX, vivadoRX):
    ''' gives full control for user over the two (TX and RX) Vivado consoles.
    '''
    
    print('Switching to VivadoRX')
    vivado = vivadoRX
    vivado.do('', vivadoPrompt, True)
    
    while True:
        cmd = raw_input()
        if cmd.startswith('!'):
            # Cleye command
            cmd = cmd[1:].lower()
            if cmd == 'rx':
                print('Switching to VivadoRX')
                vivado = vivadoRX
                vivado.do('', vivadoPrompt, True)
            elif cmd == 'tx':
                print('Switching to VivadoTX')
                vivado = vivadoTX
                vivado.do('', vivadoPrompt, True)
            elif cmd in ['q', 'quit', 'exit']:
                print('Exiting to VivadoTX')
                vivadoTX.exit()
                print('Exiting to VivadoRX')
                vivadoRX.exit()
                break
        else:
            # Vivado command
            vivado.do(cmd, vivadoPrompt, True)
    
    
if __name__ == '__main__':
    print(cleyeLogo)
    
    try:    
        logging.info('Spawning Vivado instances (TX/RX)')
        vivadoTX = Vivado(vivadoPath, vivadoArgs)
        vivadoRX = Vivado(vivadoPath, vivadoArgs)

        logging.info('Warning for prompt of Vivado (waiting for Vivado startup)')
        vivadoTX.waitStartup()
        vivadoRX.waitStartup()

        vivadoRX.do('source sourceme.tcl')
        vivadoTX.do('source sourceme.tcl')
        vivadoRX.do('set devices [fetch_devices]')
        try:
            devices = vivadoRX.get_var('devices')
        except:
            logging.error('No target device found. Please connect and power up your device(s)')
            raise

        # Get a list of all devices on all target.
        # Remove the brackets. (fetch_devices returns lists.)
        devices = re.findall(r'\{(.+?)\}', devices[0]) 
        # devices = [x[1:-1] for x in devices[0].split(' ') ]

        #
        # Choose TX/RX device
        # 
        vivadoTX.chooseDevice(devices, 'TX')
        vivadoRX.chooseDevice(devices, 'RX')

        #
        # Choose SIOs
        # 
        txSio = vivadoTX.chooseSio('TX', createLink=False)
        vivadoRX.chooseSio('RX')

        independent_finder(vivadoTX, vivadoRX, txSio)

        print('')
        print('All Script has been run.')
        print('Switch to RX vivado console:')
        print('')
        
        interactiveVivadoConsole(vivadoTX, vivadoRX)
    except KeyboardInterrupt:
        print('Exiting to VivadoTX')
        vivadoTX.exit()
        print('Exiting to VivadoRX')
        vivadoRX.exit()
    except Exception:
        traceback.print_exc()
        print('Exiting to VivadoTX')
        vivadoTX.exit()
        print('Exiting to VivadoRX')
        vivadoRX.exit()
    
    
