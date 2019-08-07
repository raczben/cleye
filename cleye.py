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
#  - time for keyboard interrupt handling
#  - logging to write logs of running
import os
import re
import csv
import argparse
import traceback
import time
import logging

# Import 3th party modules:
#  - wexpect/pexpect to launch ant interact with subprocesses.
if os.name == 'nt':
    import wexpect as expect
else: # Linux
    import pexpect as expect

cleyeLogo = r'''
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
logging.basicConfig(level=logging.INFO)
logging.basicConfig(filename='cleye.log', filemode='w', format='%(asctime)s - %(name)s: [%(levelname)s] %(message)s')


class Clexeption(Exception):
    '''Cleye specific exceptions.
    '''
    pass


class Vivado():
    def __init__(self, executable, args, sideName):
        self.childProc = None
        self.sideName = sideName
        self.sio = None
        self.sioLink = None
        
        self.childProc = expect.spawn(executable, args)
        
        
    def waitStartup(self):
        self.childProc.expect(vivadoPrompt)
        # print the texts
        logging.debug(self.childProc.before + self.childProc.match.group(0))
        
        
    def do(self, cmd, prompt=vivadoPrompt, puts=False, errmsgs=[]):
        ''' do a simple command in Vivado console
        '''
        if self.childProc.terminated:
            logging.error('The process has been terminated. Sending command is not possible.')
            raise Clexeption('The process has been terminated. Sending command is not possible.')
        self.childProc.sendline(cmd)
        if prompt:
            self.childProc.expect(vivadoPrompt)
            logging.debug(cmd + self.childProc.before + self.childProc.match.group(0))
            for em in  errmsgs:
                if em in self.childProc.before:
                    logging.error('during running command: ' + cmd + self.childProc.before)
                    raise Clexeption('during running command: ' + cmd + self.childProc.before)
            if puts:
                print(cmd, end='')
                print(self.childProc.before, end='')
                print(self.childProc.match.group(0), end='')
        
        
    def chooseDevice(self, devices, vivadoPrompt=vivadoPrompt, puts=False):
        ''' set the hw target (blaster) and device (FPGA) for TX and RX side.
        '''
        # Print devices to user to choose from them.
        for i, dev in enumerate(devices):
            print(str(i) + ' ' + dev)

        print('Choose device for {}: '.format(self.sideName), end='')
        deviceId = input()
        device = devices[deviceId]

        errmsgs = ['DONE status = 0', 'The debug hub core was not detected.']
        self.do('set_device ' + device, vivadoPrompt, puts, errmsgs = errmsgs)


    def chooseSio(self, createLink=True, vivadoPrompt=vivadoPrompt, puts=False):
        ''' Set the transceiver channel for TX/RX side.
        '''
        self.do('', vivadoPrompt, puts)
        errmsgs = ['No matching hw_sio_gts were found.']
        self.do('get_hw_sio_gts', vivadoPrompt, puts, errmsgs=errmsgs)
        sios = [x for x in self.childProc.before.splitlines() if x ]
        sios = sios[0].split(' ')
        for i, sio in enumerate(sios):
            print(str(i) + ' ' + sio)
        print('Print choose a SIO for {} side : '.format(self.sideName), end='')
        sioId = input()
        self.sio = sios[sioId]

        if createLink:
            self.do('create_link ' + self.sio, vivadoPrompt, puts)
        
        
    def get_var(self, varname):
        self.do('puts $' + varname)
        ret = self.childProc.before.splitlines()
        
        # remove first line, which is always empty
        ret = ret[1:] 
        # print('>>{}<<'.format(ret))
        
        # raise exception if the variable is not exist.
        if ret[0] == 'can\'t read "{}": no such variable'.format(varname):
            raise Clexeption(ret[0])
        
        return ret

    
    def get_property(self, propName, objectName, vivadoPrompt=vivadoPrompt, puts=False):
        ''' does a get_property command in vivado terminal. 
        
        It fetches the given property and returns it.
        '''
        cmd = 'get_property {} {}'.format(propName, objectName)
        self.do(cmd, vivadoPrompt, puts)
        val = [x for x in self.childProc.before.splitlines() if x ]
        return val[0]
    
    
    def set_property(self, propName, value, objectName, vivadoPrompt=vivadoPrompt, puts=False):
        ''' Sets a property.
        '''
        cmd = 'set_property {} {} {}'.format(propName, value, objectName)
        self.do(cmd, vivadoPrompt, puts)
        
        
    def resetGT(self):
        resetName = 'PORT.GT{}RESET'.format(self.sideName)
        self.set_property(resetName, '1', '[get_hw_sio_gts  {{}}]'.format(self.sio))
        self.commit_hw_sio()
        self.set_property(resetName, '0', '[get_hw_sio_gts  {{}}]'.format(self.sio))
        self.commit_hw_sio()


    def commit_hw_sio(self):
        self.set_property('commit_hw_sio' '0' '[get_hw_sio_gts  {{}}]'.format(self.sio))
    
        
    def exit(self):
        if self.childProc.terminated:
            logging.warning('This process has been terminated.')
            return None
        else:
            self.do('exit', None)
            return self.childProc.wait()
        

class ScanStructure(dict):
    def __init__(self, filename):
        self.readCsv(filename)
        
        
    def readCsv(self, filename):
        # ret = {}
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
                    self['scanData'] = ScanStructure._parsescanRows(scanRows)
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
                    self[row[0]] = val
        
        
    @staticmethod
    def _parsescanRows(scanRows):
        scanData = {
            'scanType': scanRows[0][0],
            'x':[],
            'y':[],
            'values':[]
            }
            
        if scanData['scanType'] not in ['1d bathtub', '2d statistical']:
            logging.error('Uknnown scan type: ' + scanData['scanType'])
            raise Clexeption('Uknnown scan type: ' + scanData['scanType'])
            
        xdata = scanRows[0][1:]
        # Need to normalize, dont know why...
        divider = abs(float(xdata[0])*2)
        
        scanData['x'] = [float(x)/divider for x in scanRows[0][1:]]
        
        for r in scanRows[1:]:
            intr = [float(x) for x in r]
            scanData['y'].append(intr[0])
            scanData['values'].append(intr[1:])
           
        return scanData
        

    def _testEye(self, xLimit = 0.45, xValLimit = 0.005):
        ''' Test that the read data is an eye or not.
        A valid eye must contains 'bit errors' at the edges. If the eye is clean at +-0.500 UI, this
        definetly not an eye.
        '''
        scanData = self['scanData']
        
        # Get the indexes of the 'edge'
        # Edge means where abs(x) offset is big, bigger than 0.45.
        edgeIndexes=[i for i,x in enumerate(scanData['x']) if abs(x) > xLimit]
        if len(edgeIndexes) < 2:
            logging.warning('Too few edge indexes')
            return False
            
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


    def _getArea(self, xLimit = 0.2):
        ''' This is an improoved area meter. 
        Returns the open area of an eye even if there is no definite open eye.
        Returns the center area multiplied by the BER values. (ie the average of the center area.)
        '''
        
        scanData = self['scanData']
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
        
        return centerAvg * self['Horizontal Increment']


    def getOpenArea(self):
        if self._testEye():
            if self['Open Area'] < 1.0:
                # if the 'offitial open area' is 0 try to improove:
                return self._getArea()
            else:
                return self['Open Area']
        else:
            return 0.0
    
    
def independent_finder(vivadoTX, vivadoRX):
    ''' Runs the optimizer algorithm.
    '''
    TXDIFFSWING_values = [
        # "{269 mV (0000)}" ,
        # "{336 mV (0001)}" ,
        # "{407 mV (0010)}" ,
        # "{474 mV (0011)}" ,
        # "{543 mV (0100)}" ,
        # "{609 mV (0101)}" ,
        # "{677 mV (0110)}" ,
        # "{741 mV (0111)}" ,
        # "{807 mV (1000)}" ,
        # "{866 mV (1001)}" ,
        # "{924 mV (1010)}" ,
        "{973 mV (1011)}" ,
        "{1018 mV (1100)}",
        "{1056 mV (1101)}",
        "{1092 mV (1110)}",
        "{1119 mV (1111)}"
    ]
    
    TXPRE_values = [
        "{0.00 dB (00000)}",
        "{0.22 dB (00001)}",
        "{0.45 dB (00010)}",
        "{0.68 dB (00011)}",
        "{0.92 dB (00100)}",
        # "{1.16 dB (00101)}",
        # "{1.41 dB (00110)}",
        # "{1.67 dB (00111)}",
        # "{1.94 dB (01000)}",
        # "{2.21 dB (01001)}",
        # "{2.50 dB (01010)}",
        # "{2.79 dB (01011)}",
        # "{3.10 dB (01100)}",
        # "{3.41 dB (01101)}",
        # "{3.74 dB (01110)}",
        # "{4.08 dB (01111)}",
        # "{4.44 dB (10000)}",
        # "{4.81 dB (10001)}",
        # "{5.19 dB (10010)}",
        # "{5.60 dB (10011)}",
        # "{6.02 dB (10100)}",
        # "{6.02 dB (10101)}",
        # "{6.02 dB (10110)}",
        # "{6.02 dB (10111)}",
        # "{6.02 dB (11000)}",
        # "{6.02 dB (11001)}",
        # "{6.02 dB (11010)}",
        # "{6.02 dB (11011)}",
        # "{6.02 dB (11100)}",
        # "{6.02 dB (11101)}",
        # "{6.02 dB (11110)}",
        # "{6.02 dB (11111)}",
    ]
    
    TXPOST_values = [
        # "{0.00 dB (00000)}", 
        # "{0.22 dB (00001)}", 
        "{0.45 dB (00010)}", 
        "{0.68 dB (00011)}", 
        "{0.92 dB (00100)}", 
        "{1.16 dB (00101)}", 
        "{1.41 dB (00110)}", 
        # "{1.67 dB (00111)}", 
        # "{1.94 dB (01000)}", 
        # "{2.21 dB (01001)}", 
        # "{2.50 dB (01010)}", 
        # "{2.79 dB (01011)}", 
        # "{3.10 dB (01100)}", 
        # "{3.41 dB (01101)}", 
        # "{3.74 dB (01110)}", 
        # "{4.08 dB (01111)}", 
        # "{4.44 dB (10000)}", 
        # "{4.81 dB (10001)}", 
        # "{5.19 dB (10010)}", 
        # "{5.60 dB (10011)}", 
        # "{6.02 dB (10100)}", 
        # "{6.47 dB (10101)}", 
        # "{6.94 dB (10110)}", 
        # "{7.43 dB (10111)}", 
        # "{7.96 dB (11000)}", 
        # "{8.52 dB (11001)}", 
        # "{9.12 dB (11010)}", 
        # "{9.76 dB (11011)}", 
        # "{10.46 dB (11100)}",
        # "{11.21 dB (11101)}",
        # "{12.04 dB (11110)}",
        # "{12.96 dB (11111)}",
    ]
    
    
    RXTERM_values = [
        "{100 mV}",
        "{200 mV}",
        "{250 mV}",
        "{300 mV}",
        "{350 mV}",
        "{400 mV}",
        "{500 mV}",
        "{550 mV}",
        "{600 mV}",
        "{700 mV}",
        "{800 mV}",
        "{850 mV}",
        "{900 mV}",
        "{950 mV}",
        "{1000 mV}",
        "{1100 mV}",
    ]
    
    globalIteration = 1
    globalParameterSpace = {}
    globalParameterSpace["TXDIFFSWING"] = TXDIFFSWING_values #[0::2]
    globalParameterSpace["TXPRE"] = TXPRE_values #[0::2]
    globalParameterSpace["TXPOST"] = TXPOST_values #[0::2]
    
    if not os.path.exists("runs"):
        os.makedirs("runs")

    for i in range(globalIteration):
        for pName, pValues in globalParameterSpace.items():
            openAreas = []
            maxArea   = 0
            txSioGt = '[get_hw_sio_gts {}]'.format(vivadoTX.sio)
            bestValue = vivadoTX.get_property(pName, txSioGt)
            
            for pValue in pValues:
                # Test keyboard interrupt:
                time.sleep(0)
                
                logging.info("Create scan ({} {})".format(pName, pValue))
                vivadoTX.set_property(pName, pValue, txSioGt)
                vivadoTX.do('commit_hw_sio ' + txSioGt)
                
                checkValue = vivadoTX.get_property(pName, txSioGt)
                if checkValue not in pValue: # Readback does not contains brackets {}
                    logging.error("Something went wrong. Cannot set value {}  {} ".format(checkValue, pValue))
                    
                # set_property PORT.GTRXRESET 0 [get_hw_sio_gts  {localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y0}]
                # commit_hw_sio  [get_hw_sio_gts  {localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y0}]


                fname = "{}{}{}".format(i, pName, pValue)
                fname = re.sub('\\W', '_', fname)
                fname = "runs/" + fname + '.csv'
                
                hincr = 4
                vincr = 4
                # scanType = "1d_bathtub"
                scanType = "2d_full_eye"
                linkName = "*"
                cmd = 'run_scan "{}" {} {} {} {}'.format(fname, hincr, vincr, scanType, linkName)
                vivadoRX.do(cmd, errmsgs = ['ERROR: '])
                
                scanStruc = ScanStructure(fname)
                openArea = scanStruc.getOpenArea()
                if openArea is None:
                    logging.error('openArea is None after reading file: ' + fname)
                            
                logging.info('OpenArea: {}  (parameters: {} = {})'.format(openArea, pName, pValue))
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
    
    
def init():
    logging.info('Spawning Vivado instances (TX/RX)')
    vivadoTX = Vivado(vivadoPath, vivadoArgs, 'TX')
    vivadoRX = Vivado(vivadoPath, vivadoArgs, 'RX')

    logging.info('Warning for prompt of Vivado (waiting for Vivado startup)')
    vivadoTX.waitStartup()
    vivadoRX.waitStartup()

    logging.info('Sourcing TCL procedures.')
    vivadoRX.do('source sourceme.tcl')
    vivadoTX.do('source sourceme.tcl')
    
    return vivadoTX, vivadoRX
    
    
def fetchDevices(vivado):
    logging.info('Exploring target devices (fetch_devices: this can take a while)')
    vivadoRX.do('set devices [fetch_devices]')
    try:
        devices = vivadoRX.get_var('devices')
    except Clexeption as ex:
        raise Clexeption('No target device found. Please connect and power up your device(s)')

    # Get a list of all devices on all target.
    # Remove the brackets. (fetch_devices returns lists.)
    devices = re.findall(r'\{(.+?)\}', devices[0]) 
    return devices

    
def chooseLink(vivadoTX, vivadoRX):
    # Choose TX/RX device
    vivadoTX.chooseDevice(devices)
    vivadoRX.chooseDevice(devices)
    
    # Choose SIOs
    vivadoTX.chooseSio(createLink=False)
    vivadoRX.chooseSio()


if __name__ == '__main__':
    print(cleyeLogo)
    
    try:
        vivadoTX, vivadoRX = init()
        devices = fetchDevices(vivadoRX)
        chooseLink(vivadoTX, vivadoRX)
        independent_finder(vivadoTX, vivadoRX)
        print('')
        print('All Script has been run.')

    except KeyboardInterrupt:
        print('Exiting to VivadoTX')
        vivadoTX.exit()
        print('Exiting to VivadoRX')
        vivadoRX.exit()
    except Clexeption as ex:
        logging.error(str(ex))
        if logging.root.level <= logging.DEBUG:
            traceback.print_exc()
    except Exception:
        logging.error('Unknown error!')
        traceback.print_exc()
        
    try:
        print('Switch to RX vivado console:')
        interactiveVivadoConsole(vivadoTX, vivadoRX)
    except Clexeption as ex:
        logging.error(str(ex))
        if logging.root.level <= logging.DEBUG:
            traceback.print_exc()
    except Exception:
        logging.error('Unknown error!')
        traceback.print_exc()
        print('Exiting to VivadoTX')
        vivadoTX.exit()
        print('Exiting to VivadoRX')
        vivadoRX.exit()
    
    
