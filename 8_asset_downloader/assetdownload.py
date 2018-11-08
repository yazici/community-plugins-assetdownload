#!/usr/bin/python
# -*- coding: utf-8 -*-

""" 
**Project Name:**      MakeHuman community assets

**Product Home Page:** http://www.makehumancommunity.org

**Code Home Page:**    https://github.com/makehumancommunity/community-plugins

**Authors:**           Joel Palmius

**Copyright(c):**      Joel Palmius 2016

**Licensing:**         MIT

Abstract
--------

This plugin manages community assets

"""

import gui3d
import mh
import gui
import log
import json
import os
import re
import platform
import calendar, datetime

from progress import Progress

from core import G

mhapi = gui3d.app.mhapi

if mhapi.utility.isPython3():
    from PyQt5 import QtGui
    from PyQt5 import QtCore
    from PyQt5.QtGui import *
    from PyQt5 import QtWidgets
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
else:
    if mhapi.utility.isPySideAvailable():
        from PySide import QtGui
        from PySide import QtCore
        from PySide.QtGui import *
        from PySide.QtCore import *
    else:
        from PyQt4 import QtGui
        from PyQt4 import QtCore
        from PyQt4.QtGui import *
        from PyQt4.QtCore import *

from .assetdb import AssetDB
from .tablemodel import AssetTableModel
from .downloadtask import DownloadTask

class AssetDownloadTaskView(gui3d.TaskView):

    def __init__(self, category):
        gui3d.TaskView.__init__(self, category, 'Download assets')

        self.log = mhapi.utility.getLogChannel("assetdownload")

        self.notfound = mhapi.locations.getSystemDataPath("notfound.thumb")
        self.assetdb = AssetDB(self)

        self._setupFilterBox()
        self._setupSelectedBox()
        self._setupSyncBox()
        self._setupTable()
        self._setupDetails()

        self.currentlySelectedRemoteAsset = None
        self.isShowingDetails = False

    def _setupFilterBox(self):
        self.log.trace("Enter")
        self.filterBox = mhapi.ui.createGroupBox("Filter assets")

        self.types = [
            "pose",
            "clothes",
            "target",
            "hair",
            "teeth",
            "eyebrows",
            "eyelashes",
            "skin",
            "proxy",
            "material",
            "model",
            "rig",
            "expression"
        ]

        self.filterBox.addWidget(mhapi.ui.createLabel("\nAsset type"))
        self.cbxTypes = mhapi.ui.createComboBox(self.types, self._onTypeChange)
        self.filterBox.addWidget(self.cbxTypes)

        self.filterBox.addWidget(mhapi.ui.createLabel("\nAsset subtype"))
        self.cbxSubTypes = mhapi.ui.createComboBox(["-- any --"])
        self.filterBox.addWidget(self.cbxSubTypes)

        self.authors = ["-- any --"]
        self.authors.extend(sorted(self.assetdb.getKnownAuthors(), key=lambda s: s.lower()))

        self.filterBox.addWidget(mhapi.ui.createLabel("\nAsset author"))
        self.cbxAuthors = mhapi.ui.createComboBox(self.authors)
        self.filterBox.addWidget(self.cbxAuthors)

        yesno = ["-- any --", "yes", "no"]

        #self.filterBox.addWidget(mhapi.ui.createLabel("\nHas screenshot"))
        #self.cbxScreenshot = mhapi.ui.createComboBox(yesno)
        #self.filterBox.addWidget(self.cbxScreenshot)

        #self.filterBox.addWidget(mhapi.ui.createLabel("\nHas thumbnail"))
        #self.cbxThumb = mhapi.ui.createComboBox(yesno)
        #self.filterBox.addWidget(self.cbxThumb)

        # yesno.extend(["with new remote"])

        lic = ["-- any --","CC0", "CC-BY", "AGPL"]
        self.filterBox.addWidget(mhapi.ui.createLabel("\nAsset license"))
        self.cbxLicense = mhapi.ui.createComboBox(lic)
        self.filterBox.addWidget(self.cbxLicense)

        self.filterBox.addWidget(mhapi.ui.createLabel("\nAlready downloaded"))
        self.cbxDownloaded = mhapi.ui.createComboBox(yesno)
        self.filterBox.addWidget(self.cbxDownloaded)

        upd = ["-- any --","One week", "One month", "Three months", "One year"]
        self.filterBox.addWidget(mhapi.ui.createLabel("\nUpdated/created within"))
        self.cbxUpdated = mhapi.ui.createComboBox(upd)
        self.filterBox.addWidget(self.cbxUpdated)

        self.filterBox.addWidget(mhapi.ui.createLabel("\nTitle contains"))
        self.txtTitle = mhapi.ui.createTextEdit()
        self.filterBox.addWidget(self.txtTitle)

        self.filterBox.addWidget(mhapi.ui.createLabel("\nDescription contains"))
        self.txtDesc = mhapi.ui.createTextEdit()
        self.filterBox.addWidget(self.txtDesc)

        self.filterBox.addWidget(mhapi.ui.createLabel(" "))
        self.btnFilter = mhapi.ui.createButton("Update list")
        self.filterBox.addWidget(self.btnFilter)

        @self.btnFilter.mhEvent
        def onClicked(event):
            self._onBtnFilterClick()

        self.addLeftWidget(self.filterBox)

    def _onTypeChange(self,newValue):
        self.log.trace("Enter")
        self.log.debug("Asset type changed to",newValue)

        if newValue == "clothes":
            self.cbxSubTypes.clear()
            self.cbxSubTypes.addItem("-- any --")
            for type in self.assetdb.getKnownClothesCategories():
                self.cbxSubTypes.addItem(type)
        else:
            self.cbxSubTypes.clear()
            self.cbxSubTypes.addItem("-- any --")

    def _onBtnFilterClick(self):
        self.log.trace("Enter")
        oldlen = len(self.headers)

        author = None
        subtype = None
        changed = None
        license = None

        if self.cbxAuthors.getCurrentItem() != "-- any --":
            author = str(self.cbxAuthors.getCurrentItem())

        assetType = str(self.cbxTypes.getCurrentItem())

        if assetType == "clothes":
            subtype = str(self.cbxSubTypes.getCurrentItem())
            if subtype == "-- any --":
                subtype = None

        title = str(self.txtTitle.getText())
        if title == "":
            title = None

        desc = str(self.txtDesc.getText())
        if desc == "":
            desc = None

        if self.cbxLicense.getCurrentItem() != "-- any --":
            license = str(self.cbxLicense.getCurrentItem())

        if self.cbxUpdated.getCurrentItem() != "-- any --":
            changed = str(self.cbxUpdated.getCurrentItem())

        downloaded = str(self.cbxDownloaded.getCurrentItem())
        if downloaded == "-- any --":
            downloaded = None

        assets = self.assetdb.getFilteredAssets(assetType, author=author, subtype=subtype, title=title, isDownloaded=downloaded, desc=desc, changed=changed, license=license)

        self.data = []

        self.headers = ["node id", "author", "license", "title", "description"]

        for asset in assets:
            self.data.append( [ str(asset.getId()), asset.getAuthor(), asset.getLicense(), asset.getTitle(), asset.getDescription() ])

        self.model = AssetTableModel(self.data,self.headers)
        self.proxymodel = QSortFilterProxyModel()
        self.proxymodel.setSourceModel(self.model)
        self.tableView.setModel(self.proxymodel)

        self.tableView.columnCountChanged(oldlen, len(self.headers))
        self.tableView.resizeColumnsToContents()

        self.hasFilter = True
        self.currentlySelectedRemoteAsset = None
        self.thumbnail.setPixmap(QtGui.QPixmap(os.path.abspath(self.notfound)))

    def _setupSelectedBox(self):
        self.log.trace("Enter")
        self.selectBox = mhapi.ui.createGroupBox("Selected")

        self.thumbnail = self.selectBox.addWidget(gui.TextView())
        self.thumbnail.setPixmap(QtGui.QPixmap(os.path.abspath(self.notfound)))
        self.thumbnail.setGeometry(0,0,128,128)
        self.thumbnail.setMaximumHeight(128)
        self.thumbnail.setMaximumWidth(128)
        self.thumbnail.setScaledContents(True)

        self.selectBox.addWidget(mhapi.ui.createLabel(" "))

        self.btnDetails = mhapi.ui.createButton("View details")
        self.selectBox.addWidget(self.btnDetails)

        @self.btnDetails.mhEvent
        def onClicked(event):
            self._onBtnDetailsClick()

        self.btnDownload = mhapi.ui.createButton("Download")
        self.selectBox.addWidget(self.btnDownload)

        @self.btnDownload.mhEvent
        def onClicked(event):
            self._onBtnDownloadClick()

        self.addRightWidget(self.selectBox)

    def _onBtnDetailsClick(self):
        self.log.trace("Enter")

        if self.isShowingDetails:
            self.mainPanel.show()
            self.detailsPanel.hide()
            self.isShowingDetails = False
            self.btnDetails.setText("View details")
            return

        if self.currentlySelectedRemoteAsset is None:
            self.log.debug("No asset is selected")
            return

        title = self.currentlySelectedRemoteAsset.getTitle()
        self.log.debug("Request details for asset with title",title)

        self.mainPanel.hide()
        self.detailsPanel.show()
        self.btnDetails.setText("Hide details")
        self.isShowingDetails = True

    def _onBtnDownloadClick(self):
        self.log.trace("Enter")

        if not self.hasFilter:
            self.log.debug("Table is empty")

        if self.currentlySelectedRemoteAsset is None:
            self.log.debug("No asset is selected")

        title = self.currentlySelectedRemoteAsset.getTitle()
        self.log.debug("Request download of asset with title",title)

        currentRow = None

        indexes = self.tableView.selectionModel().selectedRows()
        for index in sorted(indexes):
            currentRow = index.row()

        if currentRow is None:
            self.log.debug("No row is selected")
            return;

        self.log.debug("Currently selected row index", currentRow)
        self.log.spam("Currently selected row data", self.data[currentRow])

        assetId = int(self.data[currentRow][0])
        assetType = str(self.cbxTypes.getCurrentItem())

        remoteAsset = self.assetdb.remoteAssets[assetType][assetId]

        self.assetdb.downloadItem(self.syncBox,remoteAsset,self._downloadItemFinished)

    def _downloadItemFinished(self):
        self.showMessage("Finished downloading")

    def _setupSyncBox(self):
        self.log.trace("Enter")
        self.syncBox = mhapi.ui.createGroupBox("Synchronize")

        syncinstr = ""
        syncinstr = syncinstr + "Before being able to\n"
        syncinstr = syncinstr + "list or download any\n"
        syncinstr = syncinstr + "assets, you need to\n"
        syncinstr = syncinstr + "download the database\n"
        syncinstr = syncinstr + "from the server.\n\n"
        syncinstr = syncinstr + "You only need to do\n"
        syncinstr = syncinstr + "this the first time\n"
        syncinstr = syncinstr + "and when you want to\n"
        syncinstr = syncinstr + "check if there are \n"
        syncinstr = syncinstr + "new assets available.\n"

        self.syncBox.addWidget(mhapi.ui.createLabel(syncinstr))

        self.btnSync = mhapi.ui.createButton("Synchronize")
        self.syncBox.addWidget(self.btnSync)

        @self.btnSync.mhEvent
        def onClicked(event):
            self._onBtnSyncClick()

        self.addRightWidget(self.syncBox)

    def _onBtnSyncClick(self):
        self.log.trace("Enter")
        self.assetdb.synchronizeRemote(self.syncBox,self._onSyncFinished,self._onSyncProgress)

    def _onSyncFinished(self):
        self.log.trace("onSyncFinished")
        self.showMessage("Asset DB is now synchronized")

        self.authors = ["-- any --"]
        self.authors.extend(sorted(self.assetdb.getKnownAuthors(), key=lambda s: s.lower()))

        self.cbxAuthors.clear()

        for author in self.authors:
            self.cbxAuthors.addItem(author)

    def _onSyncProgress(self,prog=0.0):
        self.log.trace("onSyncProgress")

    def _downloadFinished(self):
        self.log.trace("Enter")
        self.log.debug("Download finished")

    def _setupTable(self):
        self.log.trace("Enter")
        self.data = [["No filter"]]
        self.headers = ["Info"]

        self.model = AssetTableModel(self.data, self.headers)

        layout = QVBoxLayout()

        self.tableView = QTableView()
        self.tableView.setModel(self.model)
        self.tableView.clicked.connect(self._tableClick)
        self.tableView.setSelectionBehavior(QTableView.SelectRows)
        self.tableView.setSortingEnabled(True)
        self.tableView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tableView.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.addTopWidget(self.tableView)

        self.hasFilter = False

    def _setupDetails(self):
        self.log.trace("Enter")

        layout = QVBoxLayout()

        self.detailsName = mhapi.ui.createLabel("<h1>Selected title</h1>")
        layout.addWidget(self.detailsName)

        self.detailsDesc = mhapi.ui.createLabel("<p>Selected description</p>")
        self.detailsDesc.setWordWrap(True)
        layout.addWidget(self.detailsDesc)

        self.detailsExtras = mhapi.ui.createLabel("<tt>License...: Hej<br />Category...: Hopp</tt>")
        layout.addWidget(self.detailsExtras)

        self.detailsRender = gui.TextView()
        self.detailsRender.setPixmap(QPixmap(os.path.abspath(self.notfound)))
        layout.addWidget(self.detailsRender)

        layout.addStretch(1)

        self.detailsPanel = QWidget()
        self.detailsPanel.setLayout(layout)

        self.addTopWidget(self.detailsPanel)
        self.detailsPanel.hide()

    def _tableClick(self):

        self.log.trace("Table click")

        if not self.hasFilter:
            return

        currentRow = None

        indexes = self.tableView.selectionModel().selectedRows()
        for index in sorted(indexes):
            currentRow = index

        if currentRow is None:
            self.log.debug("No row is selected")
            return;

        self.log.debug("Currently selected row", currentRow)

        currentRow = self.proxymodel.mapToSource(currentRow)

        self.log.debug("Currently selected mapped row", currentRow)

        currentRow = currentRow.row()

        self.log.debug("Currently selected mapped row index", currentRow)

        self.log.spam("Currently selected row data", self.data[currentRow])

        assetId = int(self.data[currentRow][0])
        assetType = str(self.cbxTypes.getCurrentItem())

        remoteAsset = self.assetdb.remoteAssets[assetType][assetId]

        thumbPath = remoteAsset.getThumbPath()

        if thumbPath is not None:
            self.thumbnail.setPixmap(QtGui.QPixmap(os.path.abspath(thumbPath)))
        else:
            self.log.debug("Asset has no thumbnail")

        self.currentlySelectedRemoteAsset = remoteAsset

        self.detailsName.setText("<h1>" + remoteAsset.getTitle() + "</h1>")
        self.detailsDesc.setText("<p>" + remoteAsset.getDescription() + "</p>")

        extras = "<br /><br /><tt>"
        extras = extras + "<b>Author........: </b>" + remoteAsset.getAuthor() + "<br />"
        extras = extras + "<b>License.......: </b>" + remoteAsset.getLicense() + "<br />"
        extras = extras + "<b>Last changed..: </b>" + remoteAsset.getChanged() + "<br />"

        extras = extras + "</tt>"
        self.detailsExtras.setText(extras)

        render = remoteAsset.getScreenshotPath()

        if render is not None and render != "" and os.path.exists(render):
            self.detailsRender.setPixmap(QtGui.QPixmap(os.path.abspath(render)))
            self.thumbnail.setGeometry(0, 0, 128, 128)
        else:
            self.detailsRender.setPixmap(QtGui.QPixmap(os.path.abspath(self.notfound)))
            self.thumbnail.setGeometry(0, 0, 800, 600)

    def showMessage(self,message,title="Information"):
        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setText(message)
        self.msg.setWindowTitle(title)
        self.msg.setStandardButtons(QMessageBox.Ok)
        self.msg.show()

