# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask import send_file
from flask_cors import CORS
from pynetdicom import (AE, evt, AllStoragePresentationContexts,
                        debug_logger,
                        PYNETDICOM_IMPLEMENTATION_UID,
                        PYNETDICOM_IMPLEMENTATION_VERSION,
                        StoragePresentationContexts,
                        DEFAULT_TRANSFER_SYNTAXES)
from pynetdicom.sop_class import (CTImageStorage,MRImageStorage, EnhancedCTImageStorage,
                                  PatientRootQueryRetrieveInformationModelMove,
                                  StudyRootQueryRetrieveInformationModelMove,
                                  PatientRootQueryRetrieveInformationModelFind)
from pydicom import Dataset
from pydicom.tag import Tag
import os
import sys
import socket
import pyodbc
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
import configparser
import subprocess


socket.setdefaulttimeout(600)

WorkDir=os.path.realpath(os.path.dirname(sys.argv[0]))
config = configparser.ConfigParser()
config.read(WorkDir+r'\service.ini')

SERVER=config['DATABASE']['SERVER']
DATABASE=config['DATABASE']['DATABASE']
UID=config['DATABASE']['UID']
PWD=config['DATABASE']['PWD']


url=config['DEFAULT']['url']
urlGet3D=config['DEFAULT']['urlGet3D']
urlGetReport=config['DEFAULT']['urlGetReport']

PACSServer=config['PACS']['SERVER']
PACSPort=int(config['PACS']['PORT'])
PACSAETitle=config['PACS']['AE_TITLE']
PACSToMove=config['PACS']['PACSToMove']

s=config['DEFAULT']['Stations']
Stations=s.split(';')
stationsParam={}
for station in Stations:
    stationParam={}
    stationParam['StudyDescription']=config[station]['StudyDescription']
    stationParam['Modality']=config[station]['Modality']
    stationParam['SeriesDescription']=config[station]['SeriesDescription']
    stationsParam[station]=stationParam


app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False
app.debug = True

WorkDir=os.path.realpath(os.path.dirname(sys.argv[0]))

def execSQL(sql,param,needFeatch):
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+SERVER+';DATABASE='+DATABASE+';UID='+UID+';PWD='+PWD)
    cursor = cnxn.cursor()
    cursor.execute(sql)
    if needFeatch:
        rows = cursor.fetchall()
        cnxn.close()
        return rows
    else:
        try:
            ids=cursor.fetchone()[0]
        except:
            ids=None
        cnxn.commit()
        cnxn.close()
        return ids


def getStudyStatus(UID,needAll): 
    sql="SELECT [Sended],[GetedInfo],[GetedReport],[Geted3D] FROM [ThoraxPACS].[dbo].[Studies] WHERE [StudyUID]=N'"+UID+"'"
    rows = execSQL(sql,None,True)
    if needAll:
        return len(rows)
    else:
        if len(rows)>0:
            return {'Sended':rows[0][0],'GetedInfo':rows[0][1],'GetedReport':rows[0][2],'Geted3D':rows[0][3]}
        else:
            return {'Sended':0,'GetedInfo':0,'GetedReport':0,'Geted3D':0}

def insertStudy(StudyUID,PathToFiles):
    if getStudyStatus(StudyUID,True)==0:
        sql='''INSERT INTO [ThoraxPACS].[dbo].[Studies]
               ([StudyUID]
               ,[Sended]
               ,[GetedInfo]
               ,[GetedReport]
               ,[Geted3D]
               ,[PathToFiles])
         VALUES
               (\''''+StudyUID+'''\'
               ,0
               ,0
               ,0
               ,0
               ,\''''+PathToFiles+'''\')'''
        execSQL(sql,None,False)
        sql='''INSERT INTO [ThoraxPACS].[dbo].[ReportFiles] ([StudyUID]) VALUES(\''''+StudyUID+'''\')'''
        execSQL(sql,None,False)

def setStudyDownloaded(UID):
    sql='''UPDATE [ThoraxPACS].[dbo].[Studies]
           SET [DownloadedFromPACS] = 1'''+" WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)

def setStudySend(UID):
    sql='''UPDATE [ThoraxPACS].[dbo].[Studies]
           SET [Sended] = 1'''+" WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)

def setStudyGetedInfo(UID,filePath):
    sql='''UPDATE [ThoraxPACS].[dbo].[Studies]
           SET [GetedInfo] = 1'''+" WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)
    sql="UPDATE [ThoraxPACS].[dbo].[ReportFiles] SET [InfoPath]='"+filePath+"' WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)

def setStudyGeted3D(UID,filePath):
    sql='''UPDATE [ThoraxPACS].[dbo].[Studies]
           SET [Geted3D] = 1'''+" WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)
    sql="UPDATE [ThoraxPACS].[dbo].[ReportFiles] SET [Model3DPath]='"+filePath+"' WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)
    
def setStudyGetedReport(UID,filePath):
    sql='''UPDATE [ThoraxPACS].[dbo].[Studies]
           SET [GetedReport] = 1'''+" WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)
    sql="UPDATE [ThoraxPACS].[dbo].[ReportFiles] SET [ReportPath]='"+filePath+"' WHERE [StudyUID]=N'"+UID+"'"
    execSQL(sql,None,False)

def sendStudies(StudyDir,UID):
    for root, dirs, files in os.walk(StudyDir, topdown = False):
        fileNames=[]
        for name in files:
            fileNames.append(('files',open(root+'\\'+name, 'rb')))
    print('Find '+str(len(fileNames))+' files to send')
    if len(fileNames)>0:
        with requests.Session() as ses:
            http_proxy  = ""
            proxyDict = { "http"  : http_proxy}
            print('Start session')
            response  = ses.get(url, timeout=600,proxies=proxyDict)
            print('Send files')
            response  = ses.post(url, files=fileNames, timeout=600,proxies=proxyDict)
            if response.status_code==200:
                print('Get info')
                setStudySend(UID)
                with open(StudyDir+'\output.html', 'w') as f:
                    f.write(response.text)
                    f.close()
                setStudyGetedInfo(UID,StudyDir+'\output.html')
            response  = ses.get(urlGet3D, timeout=600,proxies=proxyDict)
            if response.status_code==200:
                print('Get 3D')
                with open(StudyDir+r'\3D.html', 'w') as f:
                    f.write(response.text)
                    f.close()
                setStudyGeted3D(UID,StudyDir+r'\3D.html')
            response  = ses.get(urlGetReport, timeout=600,proxies=proxyDict)
            if response.status_code==200:
                print('Get report')
                with open(StudyDir+r'\report.pdf', 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                    f.close()
                setStudyGetedReport(UID,StudyDir+r'\report.pdf')

            
        
            
def downloadStudyFromPACS(UID):  
    ae = AE()
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)

    ae.add_requested_context(EnhancedCTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
    ae.add_requested_context(CTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
    ae.add_requested_context(MRImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])

    ae.add_supported_context(EnhancedCTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
    ae.add_supported_context(CTImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
    ae.add_supported_context(MRImageStorage,['1.2.840.10008.1.2.4.57','1.2.840.10008.1.2.4.70'])
    ae.ae_title=PACSToMove
    ds = Dataset()
    ds.QueryRetrieveLevel = 'SERIES'
    ds.SeriesInstanceUID=UID
    assoc = ae.associate(PACSServer, PACSPort, ae_title=PACSAETitle)
    t1=Tag(0x00,0x1020) 
    t2=Tag(0x00,0x1021)
    if assoc.is_established:
        response = assoc.send_c_move(ds, PACSToMove, PatientRootQueryRetrieveInformationModelMove)
        for idetif,resp in response:
            try:
##                pass
                print('Done',idetif[t2].value,'stand',idetif[t1].value)
            except:
                print('PACS Move error')
    else:
        print('PACS Move assoc error')     
    assoc.release()
    
@app.route('/findSeriesUIDs')
def findSeriesUIDs():
    date=request.args.get('date')
    uids={}
    for station in Stations:
        StudyDescription=stationsParam[station]['StudyDescription']
        Modality=stationsParam[station]['Modality']
        SeriesDescription=stationsParam[station]['SeriesDescription']    
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(MRImageStorage)
        ae.ae_title='art'
        ds = Dataset()
        ds.QueryRetrieveLevel = 'SERIES'
        ds.PatientID = '*'
        ds.SeriesInstanceUID='*'
        ds.PatientName='*'
        ds.StudyDate=date
        ds.StudyTime='*'
        ds.StudyDescription=StudyDescription
        ds.Modality=Modality
        ds.SeriesDescription=SeriesDescription
        assoc = ae.associate(PACSServer, PACSPort, ae_title=PACSAETitle)
        if assoc.is_established:
            response = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)
            for (status, dataset) in response:
                
                try:
                    a=str(dataset.StudyDate)
                    b=str(dataset.StudyTime)
                    sended=getStudyStatus(dataset.SeriesInstanceUID,False)
                    uids[dataset.SeriesInstanceUID]={'PatientID':dataset.PatientID,
                                                     'PatientName':str(dataset.PatientName),
                                                     'StudyDate':a[:4]+'.'+a[4:6]+'.'+a[6:],
                                                     'StudyTime':b[:2]+':'+b[2:4]+':'+b[4:],
                                                     'status':sended}
                except:
                    pass
            assoc.release()
    return (uids)

@app.route('/sendStudies')
def sendStudiesPre():
    UID=request.args.get('UID')
    NHistory=request.args.get('PacID')
    if getStudyStatus(UID,True)>0:
        StudyDir=WorkDir+'\\'+NHistory+'_'+UID
        if os.path.exists(StudyDir):
            comand=r'RMDIR  /S /Q "'+os.path.abspath(StudyDir)+'"'
            output = subprocess.Popen(comand,shell=True)
        downloadStudyFromPACS(UID)
        setStudyDownloaded(UID)
        sendStudies(StudyDir,UID)
        ##if 
    else:
        StudyDir=WorkDir+'\\'+NHistory+'_'+UID
        insertStudy(UID,StudyDir)
        downloadStudyFromPACS(UID)
        setStudyDownloaded(UID)
        sendStudies(StudyDir,UID) 
    return UID

def getFilePath(UID,pathType):
    sql="SELECT ["+pathType+"] FROM [ThoraxPACS].[dbo].[ReportFiles] WHERE [StudyUID]=N'"+UID+"'"
    rows = execSQL(sql,None,True)
    return rows[0][0]


@app.route('/getStudyInfo')
def getStudyInfo():
    body_text=''
    UID=request.args.get('UID')
    filePath=Path(getFilePath(UID,'InfoPath'))
    with open(filePath, "r") as f:  
        contents = f.read()
        soup = BeautifulSoup(contents, 'lxml')
        tags=[]
        for tag in soup.find_all("h1"):
            tags.append(tag.text)
    body_text=body_text+'\n'+tags[1]+'\n'+tags[2]+'\n'+tags[3]
    return body_text

@app.route('/get3DModel')
def get3DModel():
    body_text=''
    UID=request.args.get('UID')
    filePath=Path(getFilePath(UID,'Model3DPath'))
    return send_file(filePath,'3D.html')

@app.route('/getReport')
def getReport():
    body_text=''
    UID=request.args.get('UID')
    filePath=Path(getFilePath(UID,'ReportPath'))
    return send_file(filePath,'Report.pdf')
    
if __name__ == "__main__":
    app.run(host='0.0.0.0')
    
