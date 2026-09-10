#IMPORT PACKAGES
import ids_peak.ids_peak as ids_peak
import ids_peak_ipl.ids_peak_ipl as ids_ipl
import numpy as np
from matplotlib import pyplot as plt
import sys
import cv2
from motion.pi import * # Define controller object E705
import time
import os

#SCAN PARAMETRES
minscan=0
maxscan=100
nscan=101

#INITIALIZE CAMERA
ids_peak.Library.Initialize()
device_manager = ids_peak.DeviceManager.Instance()
device_manager.Update()
device_descriptors = device_manager.Devices()

print("Found Devices: " + str(len(device_descriptors)))
if len(device_descriptors)==0:
    sys.exit() 
    
for device_descriptor in device_descriptors:
    print(device_descriptor.DisplayName()) # Print all of devices
    
device = device_descriptors[0].OpenDevice(ids_peak.DeviceAccessType_Exclusive) # Using only device [0] 
print("Opened Device: " + device.DisplayName())
remote_device_nodemap = device.RemoteDevice().NodeMaps()[0]

#SET SOFTWARE TRIGGER MODE
remote_device_nodemap.FindNode("TriggerSelector").SetCurrentEntry("ExposureStart")
remote_device_nodemap.FindNode("TriggerSource").SetCurrentEntry("Software")
remote_device_nodemap.FindNode("TriggerMode").SetCurrentEntry("On")

#START IMAGE ACQUISITION
datastream = device.DataStreams()[0].OpenDataStream()
payload_size = remote_device_nodemap.FindNode("PayloadSize").Value()
for i in range(datastream.NumBuffersAnnouncedMinRequired()):
    buffer = datastream.AllocAndAnnounceBuffer(payload_size)
    datastream.QueueBuffer(buffer)
    
datastream.StartAcquisition()
remote_device_nodemap.FindNode("AcquisitionStart").Execute()
remote_device_nodemap.FindNode("AcquisitionStart").WaitUntilDone()

#CHANGE CAMERA SETTINGS 
#Exposure Time
remote_device_nodemap.FindNode("ExposureTime").SetValue(20000) # In microseconds

#TRIGGER IMAGE
remote_device_nodemap.FindNode("TriggerSoftware").Execute()
buffer = datastream.WaitForFinishedBuffer(1000)

#CONVERT TO RGB
raw_image = ids_ipl.Image.CreateFromSizeAndBuffer(buffer.PixelFormat(), buffer.BasePtr(), buffer.Size(), buffer.Width(), buffer.Height())
color_image = raw_image.ConvertTo(ids_ipl.PixelFormatName_RGB8)
datastream.QueueBuffer(buffer)

#PARAMETERS
cal=np.linspace(minscan,maxscan,nscan)  # Range (min,max,number of points)

### Creation of piezo object

num='0x06000500 0' #  Numerical mode 'SPA Z 0x06000500 0'
z_axis=E709() # Creation of controller object E709
time.sleep(0.3)
# Switch to numerical mode
z_axis.serial.send(b' '.join((b'SPA 1', str(num).encode('ascii'))))  

time.sleep(0.3)
for i in cal:
    z_axis.target=maxscan-i
    i=format(i,'g')
    print("target = " + str(i) + " µm")
    time.sleep(0.1)
    
    # Trigger image
    remote_device_nodemap.FindNode("TriggerSoftware").Execute()
    buffer = datastream.WaitForFinishedBuffer(1000)

    # Convert to RGB
    raw_image = ids_ipl.Image.CreateFromSizeAndBuffer(buffer.PixelFormat(), buffer.BasePtr(), buffer.Size(), buffer.Width(), buffer.Height())
    color_image = raw_image.ConvertTo(ids_ipl.PixelFormatName_RGB8)
    datastream.QueueBuffer(buffer)

    picture = color_image.get_numpy_3D()

    plt.imshow(picture)
    cv2.imwrite('/home/lou-hannah_dichant/Documents/Zpile/images/im'+str(i)+'.jpg',picture)
    j=i
		
    if j==cal[-1]:
        break


z_axis.target=maxscan

### Stop acquisition cleanly
try:
    stop_node = remote_device_nodemap.FindNode("AcquisitionStop")
    stop_node.Execute()
    stop_node.WaitUntilDone()
except Exception as e:
    print("AcquisitionStop error (non critique):", e)

# Stop / flush datastream
try:
    datastream.StopAcquisition()
except Exception as e:
    print("datastream.StopAcquisition() a levé :", e)

# Empty/revoke buffers
try:
    if hasattr(datastream, "Flush"):
        datastream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
    if hasattr(datastream, "RevokeAllBuffers"):
        datastream.RevokeAllBuffers()
except Exception as e:
    print("Erreur lors du nettoyage des buffers :", e)

time.sleep(0.1)

try:
    node = remote_device_nodemap.FindNode("TriggerMode")
    entries = [node.GetEntry(i).GetSymbolic() for i in range(node.GetEntryCount())]
    print("TriggerMode entries disponibles :", entries)

    node.SetCurrentEntry("Off")
    node.SetCurrentEntry("Freerun")
    print("TriggerMode modifié avec succès.")
except Exception as e:
    print("Impossible de changer TriggerMode :", e)


ids_peak.Library.Close()