# -*- coding: utf-8 -*-
import sys 
from PyQt5 import QtWidgets, QtGui, QtCore
import myUI
import requests
import json
from datetime import datetime
import pyodbc
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
import configparser
import os
from QNotifications import QNotificationArea

WorkDir=os.path.realpath(os.path.dirname(sys.argv[0]))
config = configparser.ConfigParser()
config.read(WorkDir+r'\thoraxPACS.ini')
server=config['DEFAULT']['Server']
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = WorkDir+r'\lib\PyQt5\Qt\plugins\platforms'


class WebView(QtWidgets.QDialog, myUI.Web_Form):
    def  __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(WorkDir+r'\lung.png'))

class TaskThread(QtCore.QThread):
    taskFinished = QtCore.pyqtSignal()
    def __init__(self, UID,PacId, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.UID=UID
        self.PacId=PacId
    def run(self):
        session = requests.Session()
        session.trust_env = False
        r = session.get(server+'/sendStudies',
                         params={'UID': self.UID,
                                 'PacID':self.PacId})
        self.taskFinished.emit() 


class progressBar(QtWidgets.QDialog,myUI.progressForm):
    def  __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(WorkDir+r'\lung.png'))
        
class ExampleApp(QtWidgets.QWidget, myUI.Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(WorkDir+r'\lung.png'))
        self.searchButton.clicked.connect(self.searchUIDs)
        self.sendButton.clicked.connect(self.sendStudy)
        self.get3DModelButton.clicked.connect(self.get3DModel)
        self.getReportButton.clicked.connect(self.getReport)
        self.tableWidget.clicked.connect(self.buttonEnable)
        self.tableWidget.doubleClicked.connect(self.getInfo)
##        self.dateEdit.dateChanged.connect(self.searchUIDs)
        self.tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        data=datetime.now()
        year=data.year
        month=data.month
        day=data.day
        self.dateEdit.setDate(QtCore.QDate(year,month,day))
        self.dateEdit.dateChanged.connect(self.searchUIDs)
        self.studies={}
        self.messageBox = QNotificationArea(self.tableWidget)
        self.messageBox.setEntryEffect('fadeIn', 500)
        self.messageBox.setExitEffect('fadeOut', 1000)
        self.searchButton.setVisible(False)
        

    def onStart(self,UID,PacId):
        self.progress = progressBar()
        self.progress.progressBar.setRange(0,0)
        self.progress.setWindowTitle('Отправка исследования по пациенту '+PacId)
        self.progress.show()
        self.myLongTask = TaskThread(UID=UID,PacId=PacId)
        self.myLongTask.taskFinished.connect(self.onFinished)     
        self.myLongTask.start()
        
    def onFinished(self):
        self.progress.progressBar.setRange(0,1)
        self.progress.close()
        self.searchUIDs()

    def getReport(self):
        row=self.tableWidget.currentRow()
        UID=self.tableWidget.item(row, 0).text()
        if self.studies[UID]['status']['GetedReport']==1:
            auth = WebView()
            auth.browser.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
            auth.browser.load(QtCore.QUrl(server+"/getReport?UID="+UID))
            auth.exec_()

    
    def buttonEnable(self):
        row=self.tableWidget.currentRow()
        UID=self.tableWidget.item(row, 0).text()
        if self.tableWidget.item(row, 4).checkState() == QtCore.Qt.Checked:
            if (self.studies[UID]['status']['GetedReport']==0 or
                self.studies[UID]['status']['Geted3D']==0 or
                self.studies[UID]['status']['GetedInfo']==0) :
                self.sendButton.setEnabled(True)
            else:
                self.sendButton.setEnabled(False)
        else:
            self.sendButton.setEnabled(True)
        if self.studies[UID]['status']['GetedReport']==0:
            self.getReportButton.setEnabled(False)
        else:
            self.getReportButton.setEnabled(True)
        if self.studies[UID]['status']['Geted3D']==0:
            self.get3DModelButton.setEnabled(False)
        else:
            self.get3DModelButton.setEnabled(True)
        if self.studies[UID]['status']['GetedInfo']==1:
            session = requests.Session()
            session.trust_env = False
            r = session.get(server+'/getStudyInfo',
                         params={'UID': UID})
            self.messageBox.display(r.text, 'primary', 2000)

    def get3DModel(self):
        row=self.tableWidget.currentRow()
        UID=self.tableWidget.item(row, 0).text()
        if self.studies[UID]['status']['Geted3D']==1:
            auth = WebView()
            auth.browser.load(QtCore.QUrl(server+"/get3DModel?UID="+UID))
            auth.exec_()

        
    def setColortoRow(self, rowIndex, infoGot):
        for j in range(self.tableWidget.columnCount()):
            if infoGot:
                self.tableWidget.item(rowIndex, j).setBackground(QtGui.QColor(0,125,0))
            else:
                self.tableWidget.item(rowIndex, j).setBackground(QtGui.QColor(125,0,0))
        
    def getInfo(self):
        row=self.tableWidget.currentRow()
        UID=self.tableWidget.item(row, 0).text()
        if self.studies[UID]['status']['GetedInfo']==1:
            session = requests.Session()
            session.trust_env = False
            r = session.get(server+'/getStudyInfo',
                         params={'UID': UID})
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setWindowIcon(QtGui.QIcon(WorkDir+r'\lung.png'))
            msg.setWindowTitle('Информация о пациенте')
            msg.setText(r.text)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            retval = msg.exec_()
##            self.messageBox.display(r.text, 'info', 5000)
    
    def searchUIDs(self):
        session = requests.Session()
        session.trust_env = False
        r = session.get(server+'/findSeriesUIDs',
                         params={'date': self.dateEdit.dateTime().toString('yyyyMMdd')})
        r.encoding='utf-8'
        uids= json.loads(r.text)
        self.studies=uids
        self.tableWidget.setRowCount(0)
        for uid in uids:
            rowPosition = self.tableWidget.rowCount()
            self.tableWidget.insertRow(rowPosition)
            self.tableWidget.setItem(rowPosition , 0, QtWidgets.QTableWidgetItem(uid))
            self.tableWidget.setItem(rowPosition , 1, QtWidgets.QTableWidgetItem(uids[uid]['PatientName']))
            self.tableWidget.setItem(rowPosition , 2, QtWidgets.QTableWidgetItem(uids[uid]['PatientID']))
            fDateTime=uids[uid]['StudyDate']+' '+uids[uid]['StudyTime']
            try:
                dateTimeObj=datetime.strptime(fDateTime,'%Y.%m.%d %H:%M:%S')
            except:
                dateTimeObj=datetime.strptime(fDateTime,'%Y.%m.%d %H:%M:%S.%f')
            self.tableWidget.setItem(rowPosition , 3, QtWidgets.QTableWidgetItem(str(dateTimeObj)))
            self.tableWidget.setItem(rowPosition , 4, QtWidgets.QTableWidgetItem())
            self.tableWidget.item(rowPosition, 4).setFlags(QtCore.Qt.ItemIsUserCheckable)
            if (uids[uid]['status']['Sended'])==0:
                self.tableWidget.item(rowPosition, 4).setCheckState(QtCore.Qt.Unchecked)
            else:
                self.tableWidget.item(rowPosition, 4).setCheckState(QtCore.Qt.Checked)
                ok=(self.studies[uid]['status']['GetedReport']==1 and
                    self.studies[uid]['status']['Geted3D']==1 and
                    self.studies[uid]['status']['GetedInfo']==1)
                self.setColortoRow(rowPosition,ok)
        self.tableWidget.resizeColumnToContents(0)

    def sendStudy(self):
        row=self.tableWidget.currentRow()
        UID=self.tableWidget.item(row, 0).text()
        PacId=self.tableWidget.item(row, 2).text()
        self.onStart(UID,PacId)
        
    
        
def main():
    app = QtWidgets.QApplication(sys.argv)  
    window = ExampleApp() 
    window.show() 
    app.exec_()  

if __name__ == '__main__': 
    main() 
