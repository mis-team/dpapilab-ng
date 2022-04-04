#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright 2015, Francesco "dfirfpi" Picasso <francesco.picasso@gmail.com>
# Copyright 2021, Photubias <tijl.deneut@howest.be>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
## Also works with Domain PVK file (PriVateKey), 
##  Get it from the PDC using PowerShell:
##   "Install-Module -Name dsinternals -force; Import-Module DSInternals"
##   "Get-ADReplBackupKey -Server 192.168.1.1 -Credential (Get-Credential) | Save-DPAPIBlob -DirectoryPath ."
""" Windows DPAPI user's MasterKeys decryption utility."""

import optparse, sys, re, os, hashlib

try:
    from dpapick3 import masterkey
except ImportError:
    raise ImportError('[-] Missing dpapick3, please install via pip install dpapick3.')

def check_parameters(options, args):
    """Simple checks on the parameters set by the user."""
    if not options.sid and not options.pvk:
        try:
            options.sid = re.findall(r"S-1-\d+-\d+-\d+-\d+-\d+-\d+", args[0])[0]
            print('[+] Detected SID: ' + options.sid)
        except:
            sys.exit('[-] You must provide the user\'s SID textual string.')
    if not options.password and not options.pwdhash and not options.pvk:
        print('[!] No password provided, assuming user has no password.')
        options.pwdhash = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        #options.pwdhash = '31d6cfe0d16ae931b73c59d7e0c089c0' ## NT hash sometimes also works
    if not args:
        sys.exit('[-] You must provide at least one MasterKey file.')

def parseGUID(bData):
    def reverseByte(bByteInput):
        sReversed = ''
        sHexInput = bByteInput.hex()
        for x in range(-1, -len(str(sHexInput)), -2): sReversed += sHexInput[x-1] + sHexInput[x]
        return bytes.fromhex(sReversed)
    return reverseByte(bData[:4]).hex() + '-' + reverseByte(bData[4:6]).hex() + '-' + reverseByte(bData[6:8]).hex() + '-' + bData[8:10].hex() + '-' + bData[10:].hex()

if __name__ == '__main__':
    """Utility core."""
    usage = (
        'usage: %prog [options] MKfile1 MKfile2 etc.\n\n'
        'It tries to unlock (decrypt) *user* MasterKey files provided.\n'
        ' Default User MK location: %appdata%\\Microsoft\\Protect\\')

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--sid', '-s', help='Optional: will try to construct from MK path when not provided')
    parser.add_option('--credhist', '-c', help='Optional: Add credhist file')
    parser.add_option('--password', '-p', help='Optional: Will use empty password when not provided')
    parser.add_option('--pwdhash', '-a', help='Optional: Depending on MK; either a SHA1 or NT password hash')
    parser.add_option('--pvk', '-k', help='Optional: Depending on MK; domain RSA PVK keyfile')

    (options, args) = parser.parse_args()

    check_parameters(options, args)

    oMKP = masterkey.MasterKeyPool()
    for arg in args:
        for sFile in os.listdir(arg): 
            if sFile == 'Preferred': print('[+] Preferred Key is ' + parseGUID(open(os.path.join(arg, sFile),'rb').read())[:36])
        try: oMKP.loadDirectory(arg.replace('*',''))
        except: pass
        try: oMKP.addMasterKey(open(arg,'rb').read())
        except: pass
    print('[!] Imported {} keys'.format(str(len(list(oMKP.keys)))))
    print('    Now adding credential(s), hold on as this may take some time')
    if options.credhist: oMKP.addCredhistFile(options.sid, options.credhist)
    if options.password: oMKP.try_credential(options.sid, options.password)
    if options.pwdhash: oMKP.try_credential_hash(options.sid, bytes.fromhex(options.pwdhash))
    if options.pvk: oMKP.try_domain(options.pvk)
    
    iDecrypted = 0
    for oMKGUID in list(oMKP.keys):
        oMK = oMKP.getMasterKeys(oMKGUID)[0]
        if oMK.decrypted:
            iDecrypted+=1
            print('[+] MK decrypted: {}'.format(oMKGUID.decode(errors='ignore')))
            print('    Secret: ' + oMK.get_key().hex())
            print('    SHA1: %s' % hashlib.sha1(oMK.get_key()).hexdigest())
            #print('    SHA1: %s' % hashlib.sha1(mkey).digest().hex())
    if iDecrypted > 0: print('[+] Success. Decrypted {} out of {} keys'.format(str(iDecrypted), str(len(list(oMKP.keys)))))
    else: print('[-] No luck, try a different approach (NT hash, lsass dump, cleartext password, PVK AD cert, credhist file ...)')