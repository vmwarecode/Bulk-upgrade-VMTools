#!/usr/bin/python -u

import sys
import time

from pyVim.connect import GetSi, SmartConnect, Disconnect
from pyVim.task import WaitForTasks, WaitForTask
from pyVmomi import Vim
from vmware import vsi
from threading import Thread

MEM_SIZE = 1024

def waitForVMwareTools(vm, timeout):
   '''
   Wait for VMwareTools status

   @param vm: affected virtual machine
   @param timeout: timeout for waiting for tools ready
   '''

   startTime = time.time()
   timeoutAt = timeout + startTime
   while time.time() < timeoutAt:
      # If status is green, tools are running
      if vm.GetGuestHeartbeatStatus() == "green":
         print ("[INFO]Tool ready in: %s seconds." % (time.time() - startTime))
         return True
      time.sleep(.1)

   print ('[ERROR]Waiting for tool for more than 40 minutes!!!')
   return False

def waitAndUpgradeVMwareTools(vm, oldVersions, timeout):
   '''
   Wait for VMwareTools startup and upgrade to latest version.

   @param vm: affected virtual machine
   @param timeout: timeout for waiting for tools ready
   '''

   if not waitForVMwareTools(vm, timeout):
      print ('[ERROR]Unable to upgrade tools.')
      return

   oldVersions.append(vm.GetGuest().GetToolsVersion())
   print ('[DEBUG][old]Tool version is: %s. Start upgrade...' % str(oldVersions[-1]))
   WaitForTask(vm.UpgradeTools())

def waitAndGetToolsVersion(vm, newVersions, timeout):

   if not waitForVMwareTools(vm, timeout):
      print ('[ERROR]Unable to get new tools version.')
      return

   newVersions.append(vm.GetGuest().GetToolsVersion())
   print ('[DEBUG][new]Tool version is: %s' % str(newVersions[-1]))


if __name__ == '__main__':

   ret = 0
   configs = []
   records = []
   vmlist = []
   vms = []
   oldVersions = []
   newVersions = []
   threads = []
   timeout = 2400
   si = SmartConnect()

   try:
      # find vms in inventory, reconfigure and power on them
      for vm in si.content.rootFolder.childEntity[0].vmFolder.childEntity:
         vmlist.append(vm)

      print ('[INFO]Total %d VMs in this test.' % len(vmlist))


      print ('[INFO]Power on VMs.')
      WaitForTasks([vm.PowerOn() for vm in vmlist if vm.summary.runtime.powerState == 'poweredOff'])

      print ('[INFO]Upgrade tools.')
      for vm in vmlist:
         threads.append(Thread(target=waitAndUpgradeVMwareTools, args=(vm, oldVersions, timeout)))
      for t in threads:
         t.start()
      for t in threads:
         t.join()

      print ('[INFO]Finish upgrading tools.')
      print ('[INFO]Waiting for tools and recording vm new tool versions...')
      for vm in vmlist:
         records.append(Thread(target=waitAndGetToolsVersion, args=(vm, newVersions, timeout)))
      for r in records:
         r.start()
      for r in records:
         r.join()
      print ('[DEBUG]New version list length: %d' % len(newVersions))

      print ('[INFO]Checking whether tool-upgrade is successful for all VMs...')
      for i in range(len(vmlist)):
         if int(oldVersions[i]) >= int(newVersions[i]):
            print ('[DEBUG]old[%d]:%d; new[%d]:%d' % (i, int(oldVersions[i]), i, int(newVersions[i])))
            print ('[ERROR]upgrade tools failed!')
            ret = 1
            break
         else:
            continue

   except Exception as e:
      print ('[ERROR]Upgrade tools test failed! Reason: %s' % str(e))
      ret = 1

   finally:
      tasks = []

      if ret == 0:
         print ('[INFO]upgrade tools success!')

      Disconnect(GetSi())

   sys.exit(ret)
