# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
    QLCDNumber, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QSizePolicy, QStackedWidget,
    QStatusBar, QVBoxLayout, QWidget)
import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1025, 600)
        MainWindow.setStyleSheet(u"")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setMouseTracking(False)
        self.centralwidget.setStyleSheet(u"")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.title_frame = QFrame(self.centralwidget)
        self.title_frame.setObjectName(u"title_frame")
        self.title_frame.setMinimumSize(QSize(0, 0))
        self.title_frame.setMaximumSize(QSize(16777215, 40))
        self.title_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.title_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.title_frame.setLineWidth(1)
        self.horizontalLayout = QHBoxLayout(self.title_frame)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.title_icon = QLabel(self.title_frame)
        self.title_icon.setObjectName(u"title_icon")
        self.title_icon.setMinimumSize(QSize(50, 0))
        self.title_icon.setMaximumSize(QSize(50, 16777215))
        self.title_icon.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.horizontalLayout.addWidget(self.title_icon)

        self.title_label = QLabel(self.title_frame)
        self.title_label.setObjectName(u"title_label")
        self.title_label.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout.addWidget(self.title_label)

        self.pushButton = QPushButton(self.title_frame)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMinimumSize(QSize(50, 40))
        self.pushButton.setMaximumSize(QSize(50, 40))

        self.horizontalLayout.addWidget(self.pushButton)


        self.gridLayout.addWidget(self.title_frame, 0, 0, 1, 1)

        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.stackedWidget.setEnabled(True)
        self.stackedWidget.setLineWidth(0)
        self.orders_page = QWidget()
        self.orders_page.setObjectName(u"orders_page")
        self.verticalLayout_2 = QVBoxLayout(self.orders_page)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.orders_top_frame = QFrame(self.orders_page)
        self.orders_top_frame.setObjectName(u"orders_top_frame")
        self.orders_top_frame.setMinimumSize(QSize(0, 100))
        self.orders_top_frame.setMaximumSize(QSize(16777215, 110))
        self.orders_top_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.orders_top_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.orders_top_frame)
        self.gridLayout_2.setSpacing(0)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(1, 1, 1, 1)
        self.lcdNumber_11 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_11.setObjectName(u"lcdNumber_11")
        self.lcdNumber_11.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_11, 2, 16, 1, 1)

        self.lcdNumber = QLCDNumber(self.orders_top_frame)
        self.lcdNumber.setObjectName(u"lcdNumber")
        self.lcdNumber.setMinimumSize(QSize(64, 23))
        self.lcdNumber.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber.setLineWidth(1)
        self.lcdNumber.setSmallDecimalPoint(False)
        self.lcdNumber.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)

        self.gridLayout_2.addWidget(self.lcdNumber, 1, 1, 1, 1)

        self.lcdNumber_8 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_8.setObjectName(u"lcdNumber_8")
        self.lcdNumber_8.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_8, 2, 11, 1, 1)

        self.lcdNumber_44 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_44.setObjectName(u"lcdNumber_44")
        self.lcdNumber_44.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_44, 1, 12, 1, 1)

        self.label_9 = QLabel(self.orders_top_frame)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_2.addWidget(self.label_9, 1, 10, 1, 1)

        self.label_6 = QLabel(self.orders_top_frame)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_2.addWidget(self.label_6, 1, 5, 1, 1)

        self.label = QLabel(self.orders_top_frame)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 1, 0, 1, 1)

        self.lcdNumber_6 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_6.setObjectName(u"lcdNumber_6")
        self.lcdNumber_6.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_6, 3, 6, 1, 1)

        self.lcdNumber_7 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_7.setObjectName(u"lcdNumber_7")
        self.lcdNumber_7.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_7, 1, 11, 1, 1)

        self.lcdNumber_40 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_40.setObjectName(u"lcdNumber_40")
        self.lcdNumber_40.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_40, 1, 7, 1, 1)

        self.label_8 = QLabel(self.orders_top_frame)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_2.addWidget(self.label_8, 3, 5, 1, 1)

        self.lcdNumber_2 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_2.setObjectName(u"lcdNumber_2")
        self.lcdNumber_2.setMinimumSize(QSize(64, 24))
        self.lcdNumber_2.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_2.setLineWidth(1)
        self.lcdNumber_2.setSmallDecimalPoint(False)

        self.gridLayout_2.addWidget(self.lcdNumber_2, 2, 1, 1, 1)

        self.lcdNumber_43 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_43.setObjectName(u"lcdNumber_43")
        self.lcdNumber_43.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_43, 2, 12, 1, 1)

        self.lcdNumber_9 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_9.setObjectName(u"lcdNumber_9")
        self.lcdNumber_9.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_9, 3, 11, 1, 1)

        self.label_15 = QLabel(self.orders_top_frame)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout_2.addWidget(self.label_15, 1, 15, 1, 1)

        self.lcdNumber_41 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_41.setObjectName(u"lcdNumber_41")
        self.lcdNumber_41.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_41, 2, 7, 1, 1)

        self.label_7 = QLabel(self.orders_top_frame)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_2.addWidget(self.label_7, 2, 5, 1, 1)

        self.lcdNumber_10 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_10.setObjectName(u"lcdNumber_10")
        self.lcdNumber_10.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_10, 1, 16, 1, 1)

        self.label_10 = QLabel(self.orders_top_frame)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_2.addWidget(self.label_10, 2, 10, 1, 1)

        self.lcdNumber_3 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_3.setObjectName(u"lcdNumber_3")
        self.lcdNumber_3.setMinimumSize(QSize(64, 23))
        self.lcdNumber_3.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_3, 3, 1, 1, 1)

        self.lcdNumber_39 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_39.setObjectName(u"lcdNumber_39")
        self.lcdNumber_39.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_39.setLineWidth(1)
        self.lcdNumber_39.setSmallDecimalPoint(False)
        self.lcdNumber_39.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)

        self.gridLayout_2.addWidget(self.lcdNumber_39, 3, 3, 1, 1)

        self.label_3 = QLabel(self.orders_top_frame)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 3, 0, 1, 1)

        self.label_12 = QLabel(self.orders_top_frame)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.label_12, 0, 10, 1, 3)

        self.label_2 = QLabel(self.orders_top_frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 2, 0, 1, 1)

        self.lcdNumber_38 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_38.setObjectName(u"lcdNumber_38")
        self.lcdNumber_38.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_38, 1, 3, 1, 1)

        self.lcdNumber_45 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_45.setObjectName(u"lcdNumber_45")
        self.lcdNumber_45.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_45, 3, 12, 1, 1)

        self.lcdNumber_12 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_12.setObjectName(u"lcdNumber_12")
        self.lcdNumber_12.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_12, 3, 16, 1, 1)

        self.label_11 = QLabel(self.orders_top_frame)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_2.addWidget(self.label_11, 3, 10, 1, 1)

        self.label_4 = QLabel(self.orders_top_frame)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.label_4, 0, 0, 1, 3)

        self.lcdNumber_4 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_4.setObjectName(u"lcdNumber_4")
        self.lcdNumber_4.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_4, 1, 6, 1, 1)

        self.label_5 = QLabel(self.orders_top_frame)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.label_5, 0, 5, 1, 3)

        self.lcdNumber_37 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_37.setObjectName(u"lcdNumber_37")
        self.lcdNumber_37.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_37.setLineWidth(1)
        self.lcdNumber_37.setSmallDecimalPoint(False)

        self.gridLayout_2.addWidget(self.lcdNumber_37, 2, 3, 1, 1)

        self.lcdNumber_5 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_5.setObjectName(u"lcdNumber_5")
        self.lcdNumber_5.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_5, 2, 6, 1, 1)

        self.lcdNumber_42 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_42.setObjectName(u"lcdNumber_42")
        self.lcdNumber_42.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_42, 3, 7, 1, 1)

        self.label_17 = QLabel(self.orders_top_frame)
        self.label_17.setObjectName(u"label_17")

        self.gridLayout_2.addWidget(self.label_17, 3, 15, 1, 1)

        self.label_16 = QLabel(self.orders_top_frame)
        self.label_16.setObjectName(u"label_16")

        self.gridLayout_2.addWidget(self.label_16, 2, 15, 1, 1)

        self.lcdNumber_46 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_46.setObjectName(u"lcdNumber_46")
        self.lcdNumber_46.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_46, 1, 17, 1, 1)

        self.lcdNumber_48 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_48.setObjectName(u"lcdNumber_48")
        self.lcdNumber_48.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_48, 3, 17, 1, 1)

        self.lcdNumber_47 = QLCDNumber(self.orders_top_frame)
        self.lcdNumber_47.setObjectName(u"lcdNumber_47")
        self.lcdNumber_47.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_2.addWidget(self.lcdNumber_47, 2, 17, 1, 1)

        self.label_13 = QLabel(self.orders_top_frame)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.label_13, 0, 15, 1, 3)


        self.verticalLayout_2.addWidget(self.orders_top_frame)

        self.orders_midle_frame_1 = QFrame(self.orders_page)
        self.orders_midle_frame_1.setObjectName(u"orders_midle_frame_1")
        self.orders_midle_frame_1.setMouseTracking(True)
        self.orders_midle_frame_1.setTabletTracking(True)
        self.orders_midle_frame_1.setStyleSheet(u"")
        self.orders_midle_frame_1.setFrameShape(QFrame.Shape.StyledPanel)
        self.orders_midle_frame_1.setFrameShadow(QFrame.Shadow.Raised)

        self.verticalLayout_2.addWidget(self.orders_midle_frame_1)

        self.orders_midle_frame_2 = QFrame(self.orders_page)
        self.orders_midle_frame_2.setObjectName(u"orders_midle_frame_2")
        self.orders_midle_frame_2.setMaximumSize(QSize(16777215, 50))
        self.orders_midle_frame_2.setFrameShape(QFrame.Shape.StyledPanel)
        self.orders_midle_frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.orders_midle_frame_2)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.orders_midle_frame_2)

        self.orders_bottom_frame = QFrame(self.orders_page)
        self.orders_bottom_frame.setObjectName(u"orders_bottom_frame")
        self.orders_bottom_frame.setMaximumSize(QSize(16777215, 40))
        self.orders_bottom_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.orders_bottom_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_3 = QGridLayout(self.orders_bottom_frame)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setHorizontalSpacing(5)
        self.gridLayout_3.setVerticalSpacing(0)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.orders_bottom_frame)

        self.stackedWidget.addWidget(self.orders_page)
        self.daboard_page = QWidget()
        self.daboard_page.setObjectName(u"daboard_page")
        self.verticalLayout_3 = QVBoxLayout(self.daboard_page)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.daboard_top_frame = QFrame(self.daboard_page)
        self.daboard_top_frame.setObjectName(u"daboard_top_frame")
        self.daboard_top_frame.setMinimumSize(QSize(0, 100))
        self.daboard_top_frame.setMaximumSize(QSize(16777215, 110))
        self.daboard_top_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.daboard_top_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_4 = QGridLayout(self.daboard_top_frame)
        self.gridLayout_4.setSpacing(0)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.label_18 = QLabel(self.daboard_top_frame)
        self.label_18.setObjectName(u"label_18")
        self.label_18.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_4.addWidget(self.label_18, 0, 3, 3, 3)

        self.lcdNumber_31 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_31.setObjectName(u"lcdNumber_31")
        self.lcdNumber_31.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_31, 10, 13, 1, 1)

        self.label_64 = QLabel(self.daboard_top_frame)
        self.label_64.setObjectName(u"label_64")

        self.gridLayout_4.addWidget(self.label_64, 4, 12, 1, 1)

        self.lcdNumber_36 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_36.setObjectName(u"lcdNumber_36")
        self.lcdNumber_36.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_36, 7, 15, 1, 1)

        self.lcdNumber_22 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_22.setObjectName(u"lcdNumber_22")
        self.lcdNumber_22.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_22, 3, 7, 2, 1)

        self.label_20 = QLabel(self.daboard_top_frame)
        self.label_20.setObjectName(u"label_20")

        self.gridLayout_4.addWidget(self.label_20, 8, 6, 3, 2)

        self.label_52 = QLabel(self.daboard_top_frame)
        self.label_52.setObjectName(u"label_52")

        self.gridLayout_4.addWidget(self.label_52, 5, 6, 3, 2)

        self.lcdNumber_29 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_29.setObjectName(u"lcdNumber_29")
        self.lcdNumber_29.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_29, 6, 5, 2, 1)

        self.lcdNumber_27 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_27.setObjectName(u"lcdNumber_27")
        self.lcdNumber_27.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_27.setLineWidth(1)
        self.lcdNumber_27.setSmallDecimalPoint(False)
        self.lcdNumber_27.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)

        self.gridLayout_4.addWidget(self.lcdNumber_27, 3, 4, 2, 1)

        self.lcdNumber_20 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_20.setObjectName(u"lcdNumber_20")
        self.lcdNumber_20.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_20, 3, 8, 2, 2)

        self.label_61 = QLabel(self.daboard_top_frame)
        self.label_61.setObjectName(u"label_61")

        self.gridLayout_4.addWidget(self.label_61, 3, 3, 2, 1)

        self.label_56 = QLabel(self.daboard_top_frame)
        self.label_56.setObjectName(u"label_56")
        self.label_56.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_4.addWidget(self.label_56, 1, 0, 1, 3)

        self.lcdNumber_16 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_16.setObjectName(u"lcdNumber_16")
        self.lcdNumber_16.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_16, 3, 2, 2, 1)

        self.label_54 = QLabel(self.daboard_top_frame)
        self.label_54.setObjectName(u"label_54")
        self.label_54.setMinimumSize(QSize(60, 0))

        self.gridLayout_4.addWidget(self.label_54, 7, 0, 1, 1)

        self.lcdNumber_26 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_26.setObjectName(u"lcdNumber_26")
        self.lcdNumber_26.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_26, 9, 5, 2, 1)

        self.label_19 = QLabel(self.daboard_top_frame)
        self.label_19.setObjectName(u"label_19")
        self.label_19.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_4.addWidget(self.label_19, 0, 6, 2, 4)

        self.label_59 = QLabel(self.daboard_top_frame)
        self.label_59.setObjectName(u"label_59")

        self.gridLayout_4.addWidget(self.label_59, 6, 3, 2, 1)

        self.label_46 = QLabel(self.daboard_top_frame)
        self.label_46.setObjectName(u"label_46")
        self.label_46.setMinimumSize(QSize(60, 0))

        self.gridLayout_4.addWidget(self.label_46, 10, 0, 1, 1)

        self.label_49 = QLabel(self.daboard_top_frame)
        self.label_49.setObjectName(u"label_49")

        self.gridLayout_4.addWidget(self.label_49, 2, 6, 3, 2)

        self.label_62 = QLabel(self.daboard_top_frame)
        self.label_62.setObjectName(u"label_62")

        self.gridLayout_4.addWidget(self.label_62, 9, 3, 2, 1)

        self.label_51 = QLabel(self.daboard_top_frame)
        self.label_51.setObjectName(u"label_51")
        self.label_51.setMinimumSize(QSize(60, 0))

        self.gridLayout_4.addWidget(self.label_51, 4, 0, 1, 1)

        self.lcdNumber_23 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_23.setObjectName(u"lcdNumber_23")
        self.lcdNumber_23.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_23, 6, 8, 2, 2)

        self.lcdNumber_35 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_35.setObjectName(u"lcdNumber_35")
        self.lcdNumber_35.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_35, 4, 13, 1, 1)

        self.lcdNumber_18 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_18.setObjectName(u"lcdNumber_18")
        self.lcdNumber_18.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_18, 6, 2, 2, 1)

        self.lcdNumber_19 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_19.setObjectName(u"lcdNumber_19")
        self.lcdNumber_19.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_19, 6, 7, 2, 1)

        self.lcdNumber_24 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_24.setObjectName(u"lcdNumber_24")
        self.lcdNumber_24.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_24.setLineWidth(1)
        self.lcdNumber_24.setSmallDecimalPoint(False)

        self.gridLayout_4.addWidget(self.lcdNumber_24, 6, 1, 3, 1)

        self.lcdNumber_14 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_14.setObjectName(u"lcdNumber_14")
        self.lcdNumber_14.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_14, 9, 7, 2, 1)

        self.lcdNumber_30 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_30.setObjectName(u"lcdNumber_30")
        self.lcdNumber_30.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_30, 3, 5, 2, 1)

        self.lcdNumber_21 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_21.setObjectName(u"lcdNumber_21")
        self.lcdNumber_21.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_21.setLineWidth(1)
        self.lcdNumber_21.setSmallDecimalPoint(False)
        self.lcdNumber_21.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)

        self.gridLayout_4.addWidget(self.lcdNumber_21, 4, 1, 2, 1)

        self.lcdNumber_34 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_34.setObjectName(u"lcdNumber_34")
        self.lcdNumber_34.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_34, 10, 15, 1, 1)

        self.lcdNumber_32 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_32.setObjectName(u"lcdNumber_32")
        self.lcdNumber_32.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_32, 7, 13, 1, 1)

        self.lcdNumber_15 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_15.setObjectName(u"lcdNumber_15")
        self.lcdNumber_15.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_15, 9, 8, 2, 2)

        self.lcdNumber_13 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_13.setObjectName(u"lcdNumber_13")
        self.lcdNumber_13.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_13, 9, 2, 2, 1)

        self.lcdNumber_33 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_33.setObjectName(u"lcdNumber_33")
        self.lcdNumber_33.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_33, 4, 15, 1, 1)

        self.lcdNumber_17 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_17.setObjectName(u"lcdNumber_17")
        self.lcdNumber_17.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_17, 9, 1, 2, 1)

        self.label_67 = QLabel(self.daboard_top_frame)
        self.label_67.setObjectName(u"label_67")

        self.gridLayout_4.addWidget(self.label_67, 7, 12, 1, 1)

        self.lcdNumber_28 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_28.setObjectName(u"lcdNumber_28")
        self.lcdNumber_28.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout_4.addWidget(self.lcdNumber_28, 9, 4, 2, 1)

        self.label_14 = QLabel(self.daboard_top_frame)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_4.addWidget(self.label_14, 1, 9, 2, 5)

        self.lcdNumber_25 = QLCDNumber(self.daboard_top_frame)
        self.lcdNumber_25.setObjectName(u"lcdNumber_25")
        self.lcdNumber_25.setFrameShape(QFrame.Shape.NoFrame)
        self.lcdNumber_25.setLineWidth(1)
        self.lcdNumber_25.setSmallDecimalPoint(False)

        self.gridLayout_4.addWidget(self.lcdNumber_25, 6, 4, 2, 1)

        self.label_63 = QLabel(self.daboard_top_frame)
        self.label_63.setObjectName(u"label_63")

        self.gridLayout_4.addWidget(self.label_63, 10, 12, 1, 1)


        self.verticalLayout_3.addWidget(self.daboard_top_frame)

        self.daboard_midle_frame_1 = QFrame(self.daboard_page)
        self.daboard_midle_frame_1.setObjectName(u"daboard_midle_frame_1")
        self.daboard_midle_frame_1.setStyleSheet(u"")
        self.daboard_midle_frame_1.setFrameShape(QFrame.Shape.StyledPanel)
        self.daboard_midle_frame_1.setFrameShadow(QFrame.Shadow.Raised)

        self.verticalLayout_3.addWidget(self.daboard_midle_frame_1)

        self.daboard_midle_frame_2 = QFrame(self.daboard_page)
        self.daboard_midle_frame_2.setObjectName(u"daboard_midle_frame_2")
        self.daboard_midle_frame_2.setMaximumSize(QSize(16777215, 50))
        self.daboard_midle_frame_2.setFrameShape(QFrame.Shape.StyledPanel)
        self.daboard_midle_frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.daboard_midle_frame_2)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_3.addWidget(self.daboard_midle_frame_2)

        self.daboard_bottom_frame = QFrame(self.daboard_page)
        self.daboard_bottom_frame.setObjectName(u"daboard_bottom_frame")
        self.daboard_bottom_frame.setMaximumSize(QSize(16777215, 40))
        self.daboard_bottom_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.daboard_bottom_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_5 = QGridLayout(self.daboard_bottom_frame)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gridLayout_5.setHorizontalSpacing(5)
        self.gridLayout_5.setVerticalSpacing(0)
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_3.addWidget(self.daboard_bottom_frame)

        self.stackedWidget.addWidget(self.daboard_page)

        self.gridLayout.addWidget(self.stackedWidget, 0, 1, 2, 1)

        self.right_slide_menu_frame = QFrame(self.centralwidget)
        self.right_slide_menu_frame.setObjectName(u"right_slide_menu_frame")
        self.right_slide_menu_frame.setMaximumSize(QSize(16777215, 16777215))
        self.right_slide_menu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_slide_menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.right_slide_menu_frame)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)

        self.gridLayout.addWidget(self.right_slide_menu_frame, 0, 2, 2, 1)

        self.left_slide_menu_frame = QFrame(self.centralwidget)
        self.left_slide_menu_frame.setObjectName(u"left_slide_menu_frame")
        self.left_slide_menu_frame.setEnabled(True)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.left_slide_menu_frame.sizePolicy().hasHeightForWidth())
        self.left_slide_menu_frame.setSizePolicy(sizePolicy)
        self.left_slide_menu_frame.setMinimumSize(QSize(0, 0))
        self.left_slide_menu_frame.setMaximumSize(QSize(16777215, 16777215))
        self.left_slide_menu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_slide_menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.left_slide_menu_frame.setLineWidth(1)
        self.verticalLayout_6 = QVBoxLayout(self.left_slide_menu_frame)
        self.verticalLayout_6.setSpacing(0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.listWidget = QListWidget(self.left_slide_menu_frame)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setMaximumSize(QSize(16777215, 16777215))

        self.verticalLayout_6.addWidget(self.listWidget)

        self.listWidget_settings = QListWidget(self.left_slide_menu_frame)
        self.listWidget_settings.setObjectName(u"listWidget_settings")
        self.listWidget_settings.setMinimumSize(QSize(0, 0))
        self.listWidget_settings.setMaximumSize(QSize(16777215, 40))

        self.verticalLayout_6.addWidget(self.listWidget_settings)


        self.gridLayout.addWidget(self.left_slide_menu_frame, 1, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.right_slide_menu_frame.raise_()
        self.stackedWidget.raise_()
        self.left_slide_menu_frame.raise_()
        self.title_frame.raise_()
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.title_icon.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.title_label.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"PushButton", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_15.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_12.setText(QCoreApplication.translate("MainWindow", u"LOST", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"OUTPUT", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"PRODUCTIVITY", None))
        self.label_17.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_16.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_13.setText(QCoreApplication.translate("MainWindow", u"YIELD", None))
        self.label_18.setText(QCoreApplication.translate("MainWindow", u"PRODUCTIVITY", None))
        self.label_64.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_20.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_52.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_61.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_56.setText(QCoreApplication.translate("MainWindow", u"OUTPUT", None))
        self.label_54.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_19.setText(QCoreApplication.translate("MainWindow", u"LOST", None))
        self.label_59.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_46.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_49.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_62.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_51.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_67.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_14.setText(QCoreApplication.translate("MainWindow", u"YIELD", None))
        self.label_63.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
    # retranslateUi

