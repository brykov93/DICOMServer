#############################MY_SCP############################################
from pynetdicom import (AE, evt, AllStoragePresentationContexts,
                        debug_logger,
                        PYNETDICOM_IMPLEMENTATION_UID,
                        PYNETDICOM_IMPLEMENTATION_VERSION,
                        StoragePresentationContexts,
                        DEFAULT_TRANSFER_SYNTAXES)
from pynetdicom.sop_class import (CTImageStorage,MRImageStorage, EnhancedCTImageStorage,
                                  PatientRootQueryRetrieveInformationModelMove,
                                  StudyRootQueryRetrieveInformationModelMove)
from pydicom import Dataset
import os
import sys
import socket
import configparser

socket.setdefaulttimeout(600)
#debug_logger()

WorkDir=os.path.realpath(os.path.dirname(sys.argv[0]))
config = configparser.ConfigParser()
config.read(WorkDir+r'\dicomSCP.ini')
PathToStoreDCM=config['DEFAULT']['PathToStoreDCM']

def handle_store(event):
    """Handle a C-STORE request event."""
    try:
        # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
        ds = event.dataset

        # Add the File Meta Information
        ds.file_meta = event.file_meta
        fullTempPath=PathToStoreDCM+'\\'+ds.PatientID+'_'+ds.SeriesInstanceUID
        if not os.path.exists(fullTempPath):
            os.mkdir(fullTempPath)
        # Save the dataset using the SOP Instance UID as the filename
        filename=fullTempPath+'\\'+ds.SOPInstanceUID+'.dcm'
        print(filename)
        ds.PatientName=ds.PatientID
        ds.save_as(filename, write_like_original=False)
        # Return a 'Success' status
    except:
        print('error')
    return 0x0000

handlers = [(evt.EVT_C_STORE, handle_store)]
ae = AE()
ae.ae_title='art'
ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)

ae.add_requested_context(EnhancedCTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
ae.add_requested_context(CTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
ae.add_requested_context(MRImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])

ae.add_supported_context(EnhancedCTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
ae.add_supported_context(CTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
ae.add_supported_context(MRImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
print('starting')
ae.start_server(('', 11113), evt_handlers=handlers)
print('start')
