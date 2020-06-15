#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''Pychemqt, Chemical Engineering Process simulator
Copyright (C) 2009-2017, Juan José Gómez Romera <jjgomera@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''


###############################################################################
# Library with meos plugin functionality
#
#   getClassFluid: Return the thermo class to calculate
#   getMethod: Return the thermo method name to use
#   plugin: Implement meos functionality to common use in menu and dialog
#   Menu: QMenu to add to mainwindow mainmenu with all meos addon functionality
#   Dialog: QDialog with all meos functionality
#
#   Dialogs for configuration:
#   - Ui_ChooseFluid: Dialog to choose fluid for calculations
#   - Ui_ReferenceState: Dialog to select reference state
#   - DialogFilterFluid: Dialog for filter compounds family to show
#   - Dialog_InfoFluid: Dialog to show parameter of element with meos
#       - Widget_MEoS_Data: Widget to show meos data
#   - transportDialog: Dialog for transport and ancillary equations
#       - Widget_Viscosity_Data: Widget to show viscosity data
#       - Widget_Conductivity_Data: Widget to show thermal conductivity data
#   - Ui_Properties: Dialog for select and sort shown properties in tables
#
#   Table:
#   - TablaMEoS: Tabla subclass to show meos data, add context menu options
#   - Ui_Saturation: Dialog to define input for a two-phase table calculation
#   - Ui_Isoproperty: Dialog to define input for isoproperty table calculations
#   - AddPoint: Dialog to add new point to line2D
#   - createTabla: create TablaMEoS
#   - get_propiedades
#   - _getData:

#   Plot:
#   - PlotMEoS: Plot widget to show meos plot data, add context menu options
#   - Plot2D: Dialog for select a special 2D plot
#   - Plot3D: Dialog for define a 3D plot
#   - EditPlot: Dialog to edit plot
#   - AddLine: Dialog to add new isoline to plot
#   - EditAxis: Dialog to configure axes plot properties
#   - AxisWidget: Dialog to configure axes plot properties
#   - calcIsoline: Isoline calculation procedure
#   - get_points: Get point number to plot lines from Preferences
#   - getLineFormat: get matplotlib line format from preferences
#   - plotIsoline: plot isoline procedure
#   - plot2D3D: general procedure for plotting 2D and 3D
#   - _getunitTransform
#   - calcPoint
###############################################################################


from configparser import ConfigParser
from functools import partial
import gzip
import inspect
from math import ceil, floor, log10, atan, pi
import os
import pickle

from PyQt5 import QtCore, QtGui, QtWidgets
from numpy import (arange, append, concatenate, linspace,
                   logspace, transpose, delete, insert, log, nan)
from scipy.optimize import fsolve
from matplotlib.font_manager import FontProperties

from lib import meos, mEoS, coolProp, refProp, unidades, plot, config
from lib.thermo import ThermoAdvanced
from lib.utilities import representacion, exportTable, formatLine
from tools.codeEditor import SimplePythonEditor
from UI.delegate import CheckEditor
from UI.prefMEOS import Dialog as ConfDialog
from UI.widgets import (Entrada_con_unidades, createAction, LineStyleCombo,
                        MarkerCombo, ColorSelector, InputFont, Status, Tabla,
                        NumericFactor, QLabelMath)


N_PROP = len(ThermoAdvanced.properties())
KEYS = ThermoAdvanced.propertiesKey()
UNITS = ThermoAdvanced.propertiesUnit()


def getClassFluid(conf):
    """Return the thermo class to calculate
    Really return the base instance to add kwargs to calculate"""
    pref = ConfigParser()
    pref.read(config.conf_dir + "pychemqtrc")

    if pref.getboolean("MEOS", 'coolprop') and \
            pref.getboolean("MEOS", 'refprop'):
        # RefProp case, the base instance with the ids kwargs to define the
        # defined compount
        id = mEoS.__all__[conf.getint("MEoS", "fluid")].id
        fluid = refProp.RefProp(ids=[id])

    elif pref.getboolean("MEOS", 'coolprop'):
        # CoolProp case, the base instance with the ids kwargs to define the
        # defined compount
        id = mEoS.__all__[conf.getint("MEoS", "fluid")].id
        fluid = coolProp.CoolProp(ids=[id])

    else:
        # MEOS case, the instance of specified mEoS subclass
        fluid = mEoS.__all__[conf.getint("MEoS", "fluid")]()

    return fluid


def getMethod():
    """Return the thermo method name to use"""
    pref = ConfigParser()
    pref.read(config.conf_dir + "pychemqtrc")

    if pref.getboolean("MEOS", 'coolprop') and \
            pref.getboolean("MEOS", 'refprop'):
        txt = "REFPROP"
    elif pref.getboolean("MEOS", 'coolprop'):
        txt = "COOLPROP"
    else:
        txt = "MEOS"
    return txt


class plugin(object):
    """Common functionality to add to menu and dialog in main window"""

    def _txt(self):
        """Common widget names
        fTxt: Fluid name, dynamic by configuration
        refTxt: Reference state name, dynamic by configuration
        propTxt: Properties option name, fixed
        confTxt: Configure option name, fixed
        """
        if self.config.has_option("MEoS", "fluid"):
            fTxt = mEoS.__all__[self.config.getint("MEoS", "fluid")].name
        else:
            fTxt = QtWidgets.QApplication.translate("pychemqt", "Fluid")
        if self.config.has_option("MEoS", "reference"):
            refTxt = self.config.get("MEoS", "reference")
        else:
            refTxt = QtWidgets.QApplication.translate(
                "pychemqt", "Reference State")
        propTxt = QtWidgets.QApplication.translate("pychemqt", "Properties")
        confTxt = QtWidgets.QApplication.translate("pychemqt", "Configure")

        return fTxt, refTxt, propTxt, confTxt

    def _menuCalculate(self):
        """QMenu for table actions"""
        menu = QtWidgets.QMenu(QtWidgets.QApplication.translate(
            "pychemqt", "Calculate"), parent=self)
        saturationAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Saturation"),
            slot=self.showSaturation, parent=self)
        menu.addAction(saturationAction)
        IsopropertyAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Isoproperty"),
            slot=self.showIsoproperty, parent=self)
        menu.addAction(IsopropertyAction)
        menu.addSeparator()
        SpecifyAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Specified point"),
            slot=self.addTableSpecified, parent=self)
        menu.addAction(SpecifyAction)
        return menu

    def _menuPlot(self):
        """QMenu for plot actions"""
        menu = QtWidgets.QMenu(
            QtWidgets.QApplication.translate("pychemqt", "Plot"), parent=self)
        Plot_T_s_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "T-s diagram"),
            slot=partial(self.plot, "s", "T"), parent=self)
        menu.addAction(Plot_T_s_Action)
        Plot_T_rho_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "T-rho diagram"),
            slot=partial(self.plot, "rho", "T"), parent=self)
        menu.addAction(Plot_T_rho_Action)
        Plot_P_h_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "P-h diagram"),
            slot=partial(self.plot, "h", "P"), parent=self)
        menu.addAction(Plot_P_h_Action)
        Plot_P_v_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "P-v diagram"),
            slot=partial(self.plot, "v", "P"), parent=self)
        menu.addAction(Plot_P_v_Action)
        Plot_P_T_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "P-T diagram"),
            slot=partial(self.plot, "T", "P"), parent=self)
        menu.addAction(Plot_P_T_Action)
        Plot_h_s_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "h-s diagram"),
            slot=partial(self.plot, "s", "h"), parent=self)
        menu.addAction(Plot_h_s_Action)
        Plot_v_u_Action = createAction(
            QtWidgets.QApplication.translate("pychemqt", "v-u diagram"),
            slot=partial(self.plot, "u", "v"), parent=self)
        menu.addAction(Plot_v_u_Action)
        Plot2DAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Other Plots"),
            slot=self.plot2D, parent=self)
        menu.addAction(Plot2DAction)
        menu.addSeparator()
        Plot3DAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "3D Plot"),
            slot=self.plot3D, parent=self)
        menu.addAction(Plot3DAction)
        return menu

    def showChooseFluid(self):
        """Show dialog to choose/view fluid"""
        dlg = Ui_ChooseFluid(self.config)
        if dlg.exec_():
            # Update configuration
            if not self.config.has_section("MEoS"):
                self.config.add_section("MEoS")
            self.config.set("MEoS", "fluid", str(dlg.id()))
            self.config.set("MEoS", "eq", str(dlg.eq.currentIndex()))
            self.config.set("MEoS", "PR", str(dlg.radioPR.isChecked()))
            self.config.set("MEoS", "Generalized",
                            str(dlg.generalized.isChecked()))
            self.config.set("MEoS", "visco", str(dlg.visco.currentIndex()))
            self.config.set("MEoS", "thermal", str(dlg.thermal.currentIndex()))
            self.checkProperties()
            self.parent().dirty[self.parent().idTab] = True
            self.parent().saveControl()

            # Update button text in dialog case
            if self.__class__.__name__ == "Dialog":
                fTxt = mEoS.__all__[dlg.lista.currentRow()].name
                self.fluido.setText(fTxt)

    def showReference(self):
        """Show dialog to choose reference state,
        use for enthalpy and entropy zero state
        Don't implemented yet"""
        dlg = Ui_ReferenceState(self.config)
        if dlg.exec_():
            # Get values
            if not self.config.has_section("MEoS"):
                self.config.add_section("MEoS")
            if dlg.OTO.isChecked():
                refName, refT, refP, refH, refS = "OTO", 298.15, 101325, 0, 0
            elif dlg.NBP.isChecked():
                Tb = mEoS.__all__[self.config.getint("MEoS", "fluid")].Tb
                refName, refT, refP, refH, refS = "NBP", Tb, 101325, 0, 0
            elif dlg.IIR.isChecked():
                refName, refT, refP, refH, refS = "IIR", 273.15, 101325, 200, 1
            elif dlg.ASHRAE.isChecked():
                refName, refT, refP, refH, refS = "ASHRAE", 233.15, 101325,
                refH, refS = 0, 0
            else:
                refName = "Custom"
                refT = dlg.T.value
                refP = dlg.P.value
                refH = dlg.h.value
                refS = dlg.s.value

            # Update configuration
            self.config.set("MEoS", "reference", refName)
            self.config.set("MEoS", "Tref", str(refT))
            self.config.set("MEoS", "Pref", str(refP))
            self.config.set("MEoS", "ho", str(refH))
            self.config.set("MEoS", "so", str(refS))
            self.checkProperties()
            self.parent().dirty[self.parent().idTab] = True
            self.parent().saveControl()

            # Update button text in dialog case
            if self.__class__.__name__ == "Dialog":
                self.reference.setText(refName)

    def checkProperties(self):
        """Add default properties to configuration automatic when choose
        fluid or reference state and properties are not defined"""
        if not self.config.has_option("MEoS", "properties"):
            self.config.set("MEoS", "properties", str(Ui_Properties._default))
            self.config.set("MEoS", "phase", "0")
            self.config.set("MEoS", "propertiesOrder",
                            str(list(range(N_PROP))))

    def showProperties(self):
        """Show dialog to choose/sort properties to show in tables"""
        dlg = Ui_Properties(self.config)
        if dlg.exec_():
            # Update configuration
            if not self.config.has_section("MEoS"):
                self.config.add_section("MEoS")
            self.config.set("MEoS", "properties", str(dlg.properties()))
            self.config.set("MEoS", "phase", str(dlg.checkFase.isChecked()))
            self.config.set("MEoS", "propertiesOrder", str(dlg.order))
            self.parent().dirty[self.parent().idTab] = True
            self.parent().saveControl()

    def configure(self):
        """Direct access to configuration"""
        Config = ConfigParser()
        Config.read(config.conf_dir + "pychemqtrc")
        dlg = ConfDialog(Config)
        if dlg.exec_():
            Config = dlg.value(Config)
            Config.write(open(config.conf_dir+"pychemqtrc", "w"))

    def showSaturation(self):
        """Show dialog to define input for a two-phase saturation table"""
        dlg = Ui_Saturation(self.config)
        if dlg.exec_():
            # Get values
            start = dlg.Inicial.value
            end = dlg.Final.value
            incr = dlg.Incremento.value
            fix = dlg.variableFix.value
            value = arange(start, end, incr)
            if (end-start) % incr == 0:
                value = append(value, end)
            fluid = getClassFluid(self.config)
            method = getMethod()

            fluidos = []
            if dlg.VL.isChecked():
                # Liquid-Gas line
                txt = QtWidgets.QApplication.translate(
                    "pychemqt", "Liquid-Gas Line")
                if dlg.VariarTemperatura.isChecked():
                    # Changing temperature
                    for val in value:
                        vconfig = unidades.Temperature(val).str
                        self.parent().statusbar.showMessage(
                            "%s: %s =%s, %s" % (fluid.name, "T", vconfig, txt))
                        fluidos.append(fluid._new(T=val, x=0.5))
                elif dlg.VariarPresion.isChecked():
                    # Changing pressure
                    for val in value:
                        vconfig = unidades.Temperature(val).str
                        self.parent().statusbar.showMessage(
                            "%s: %s =%s, %s" % (fluid.name, "P", vconfig, txt))
                        fluidos.append(fluid._new(P=val, x=0.5))
                elif dlg.VariarXconT.isChecked():
                    # Changing quality with fixed Temperature
                    fconfig = unidades.Temperature(fix).str
                    for val in value:
                        self.parent().statusbar.showMessage(
                            "%s: T =%s  x = %s, %s" % (
                                fluid.name, fconfig, val, txt))
                        fluidos.append(fluid._new(T=fix, x=val))
                elif dlg.VariarXconP.isChecked():
                    # Changing quality with fixed pressure
                    fconfig = unidades.Temperature(fix).str
                    for val in value:
                        self.parent().statusbar.showMessage(
                            "%s: P =%s  x = %s, %s" % (
                                fluid.name, fconfig, val, txt))
                        fluidos.append(fluid._new(P=fix, x=val))

            else:
                # Melting and sublimation line, only supported for meos
                # internal method
                if dlg.SL.isChecked():
                    func = fluid._Melting_Pressure
                    txt = QtWidgets.QApplication.translate(
                        "pychemqt", "Melting Line")
                elif dlg.SV.isChecked():
                    func = fluid._Sublimation_Pressure
                    txt = QtWidgets.QApplication.translate(
                        "pychemqt", "Sublimation Line")

                if dlg.VariarTemperatura.isChecked():
                    for val in value:
                        p = func(val)
                        fluidos.append(fluid._new(T=val, P=p))
                        self.parent().statusbar.showMessage(
                            "%s: %s=%0.2f, %s" % (fluid.name, "T", val, txt))
                else:
                    for p in value:
                        T = fsolve(lambda T: p-func(T), fluid.Tt)
                        fluidos.append(fluid._new(T=T, P=p))
                        self.parent().statusbar.showMessage(
                            "%s: %s=%0.2f, %s" % (fluid.name, "P", p, txt))

            title = QtWidgets.QApplication.translate(
                "pychemqt", "Table %s: %s changing %s (%s)" % (
                    fluid.name, txt, "T", method))
            self.addTable(fluidos, title)
            self.parent().statusbar.clearMessage()

    def showIsoproperty(self):
        """Show dialog to define input for isoproperty table calculations"""
        dlg = Ui_Isoproperty(self.parent())
        if dlg.exec_():
            self.parent().updateStatus(QtWidgets.QApplication.translate(
                "pychemqt", "Launch MEoS Isoproperty calculation..."))

            # Get data from dialog
            i = dlg.fix.currentIndex()
            j = dlg.vary.currentIndex()
            if j >= i:
                j += 1
            X = dlg.keys[i]
            keys = dlg.keys[:]
            Y = keys[j]
            value1 = dlg.variableFix.value
            start = dlg.Inicial.value
            end = dlg.Final.value
            incr = dlg.Incremento.value
            value2 = arange(start, end, incr)
            if (end-start) % incr == 0:
                value2 = append(value2, end)
            v1conf = dlg.unidades[i](value1).str

            fluid = getClassFluid(self.config)
            method = getMethod()

            kwarg = {}
            # Define option parameter for transport method, only available
            # for internal meos method
            if method == "MEOS":
                for key in ("eq", "visco", "thermal"):
                    kwarg[key] = self.config.getint("MEoS", key)

            fluidos = []
            for v2 in value2:
                kwarg[X] = value1
                kwarg[Y] = v2
                if dlg.unidades[j] == float:
                    v2conf = v2
                else:
                    v2conf = dlg.unidades[j](v2).str
                self.parent().statusbar.showMessage(
                    "%s: %s =%s, %s =%s" % (fluid.name, X, v1conf, Y, v2conf))
                fluidos.append(fluid._new(**kwarg))
            unitX = dlg.unidades[i].text()
            title = QtWidgets.QApplication.translate(
                "pychemqt", "%s: %s =%s %s changing %s (%s)" % (
                    fluid.name, X, v1conf, unitX, meos.propiedades[j],
                    method))
            self.addTable(fluidos, title)

    def addTable(self, fluidos, title):
        """Add table with properties to mainwindow
        fluidos: List with fluid instances
        title: Text title for window table"""
        tabla = createTabla(self.config, title, fluidos, self.parent())
        self.parent().centralwidget.currentWidget().addSubWindow(tabla)
        wdg = self.parent().centralwidget.currentWidget().subWindowList()[-1]
        wdg.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(tabla.icon)))
        tabla.show()

    def addTableSpecified(self):
        """Add blank table to mainwindow to calculata point data"""
        fluid = getClassFluid(self.config)
        name = fluid.name
        method = getMethod()
        title = "%s: %s (%s)" % (name, QtWidgets.QApplication.translate(
            "pychemqt", "Specified state points"), method)
        tabla = createTabla(self.config, title, None, self.parent())
        tabla.Point = fluid
        self.parent().centralwidget.currentWidget().addSubWindow(tabla)
        wdg = self.parent().centralwidget.currentWidget().subWindowList()[-1]
        wdg.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(tabla.icon)))
        tabla.show()

    def plot2D(self):
        """Add a generic 2D plot to project"""
        dlg = Plot2D(self.parent())
        if dlg.exec_():
            i = dlg.ejeX.currentIndex()
            j = dlg.ejeY.currentIndex()
            if j >= i:
                j += 1
            prop = ThermoAdvanced.propertiesKey()
            x = prop[i]
            y = prop[j]

            if dlg.Xscale.isChecked():
                xscale = "log"
            else:
                xscale = "linear"
            if dlg.Yscale.isChecked():
                yscale = "log"
            else:
                yscale = "linear"
            self.plot(x, y, xscale, yscale)

    def plot3D(self):
        """Add a generic 3D plot to project"""
        dlg = Plot3D(self.parent())
        if dlg.exec_():
            i = dlg.ejeX.currentIndex()
            j = dlg.ejeY.currentIndex()
            k = dlg.ejeZ.currentIndex()
            if k >= i:
                k += 1
            if k >= j:
                k += 1
            if j >= i:
                j += 1
            prop = ThermoAdvanced.propertiesKey()
            x = prop[i]
            y = prop[j]
            z = prop[k]
            self.plot(x, y, z=z)

    def plot(self, x, y, xscale=None, yscale=None, z=""):
        """Create a plot
        x: property for axes x
        y: property for axes y
        xscale: scale for axis x
        yscale: scale for axis y
        z: property for axis z, optional to 3D plot"""
        fluid = getClassFluid(self.config)
        method = getMethod()
        filename = "%s-%s.pkl" % (method, fluid.name)

        if z:
            title = QtWidgets.QApplication.translate(
                "pychemqt", "Plot %s: %s=f(%s,%s)" % (fluid.name, z, y, x))
            dim = 3
        else:
            title = QtWidgets.QApplication.translate(
                "pychemqt", "Plot %s: %s=f(%s)" % (fluid.name, y, x))
            dim = 2
        grafico = PlotMEoS(dim=dim, parent=self.parent(), filename=filename)
        grafico.setWindowTitle(title)
        grafico.x = x
        grafico.y = y
        grafico.z = z

        unitx = UNITS[KEYS.index(x)].magnitudes()[0][0]
        unity = UNITS[KEYS.index(y)].magnitudes()[0][0]
        i = self.config.getint("Units", unitx)
        j = self.config.getint("Units", unity)
        xtxt = "%s, %s" % (x, UNITS[KEYS.index(x)].__text__[i])
        ytxt = "%s, %s" % (y, UNITS[KEYS.index(y)].__text__[j])
        grafico.plot.ax.set_xlabel(xtxt)
        grafico.plot.ax.set_ylabel(ytxt)
        if z:
            grafico.z = z
            unitz = UNITS[KEYS.index(z)].magnitudes()[0][0]
            k = self.config.getint("Units", unitz)
            ztxt = "%s, %s" % (z, UNITS[KEYS.index(z)].__text__[k])
            grafico.plot.ax.set_zlabel(ztxt)

        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Loading cached data..."))
        QtWidgets.QApplication.processEvents()
        data = grafico._getData()
        if not data:
            self.parent().progressBar.setValue(0)
            self.parent().progressBar.setVisible(True)
            self.parent().statusbar.showMessage(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Calculating data, be patient..."))
            QtWidgets.QApplication.processEvents()
            data = self.calculatePlot(fluid)
            conf = {}
            conf["method"] = method
            conf["fluid"] = self.config.getint("MEoS", "fluid")
            conf["eq"] = self.config.getint("MEoS", "eq")
            conf["visco"] = self.config.getint("MEoS", "visco")
            conf["thermal"] = self.config.getint("MEoS", "thermal")
            data["config"] = conf
            grafico._saveData(data)
            self.parent().progressBar.setVisible(False)
        self.parent().statusbar.showMessage(
            QtWidgets.QApplication.translate("pychemqt", "Plotting..."))
        QtWidgets.QApplication.processEvents()
        grafico.config = data["config"]

        if z:
            plot2D3D(grafico, data, config.Preferences, x, y, z)
        else:
            plot2D3D(grafico, data, config.Preferences, x, y)

            if not xscale:
                if x in ["P", "rho", "v"]:
                    xscale = "log"
                else:
                    xscale = "linear"
            grafico.plot.ax.set_xscale(xscale)
            if not yscale:
                if y in ["P", "rho", "v"]:
                    yscale = "log"
                else:
                    yscale = "linear"
            grafico.plot.ax.set_yscale(yscale)

        grid = config.Preferences.getboolean("MEOS", "grid")
        grafico.plot.ax._gridOn = grid
        grafico.plot.ax.grid(grid)

        self.parent().centralwidget.currentWidget().addSubWindow(grafico)
        grafico.show()
        self.parent().statusbar.clearMessage()

    def calculatePlot(self, fluid):
        """Calculate data for plot
            fluid: class of meos fluid to calculate"""
        data = {}
        points = get_points(config.Preferences)
        method = getMethod()

        # Melting and sublimation line only supported in internal meos method
        if method == "MEOS":
            # Calculate melting line
            if fluid._melting:
                self.parent().statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Calculating melting line..."))
                T = linspace(fluid._melting["Tmin"], fluid._melting["Tmax"],
                             points)
                fluidos = []
                for Ti in T:
                    P = fluid._Melting_Pressure(Ti)
                    fluido = calcPoint(fluid, self.config, T=Ti, P=P)
                    if fluido:
                        fluidos.append(fluido)
                    self.parent().progressBar.setValue(5*len(fluidos)/len(T))
                    QtWidgets.QApplication.processEvents()
                if fluidos:
                    data["melting"] = {}
                    for x in ThermoAdvanced.propertiesKey():
                        dat_propiedad = []
                        for fluido in fluidos:
                            num = fluido.__getattribute__(x)
                            if num is not None:
                                if x in ["fi", "f"]:
                                    num = num[0]
                                dat_propiedad.append(num._data)
                            else:
                                dat_propiedad.append(None)
                        data["melting"][x] = dat_propiedad

            # Calculate sublimation line
            if fluid._sublimation:
                self.parent().statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Calculating sublimation line..."))
                T = linspace(fluid._sublimation["Tmin"],
                             fluid._sublimation["Tmax"], points)
                fluidos = []
                for Ti in T:
                    P = fluid._Sublimation_Pressure(Ti)
                    fluido = calcPoint(fluid, self.config, T=Ti, P=P)
                    if fluido:
                        fluidos.append(fluido)
                    self.parent().progressBar.setValue(5+5*len(fluidos)/len(T))
                    QtWidgets.QApplication.processEvents()
                if fluidos:
                    data["sublimation"] = {}
                    for x in ThermoAdvanced.propertiesKey():
                        dat_propiedad = []
                        for fluido in fluidos:
                            num = fluido.__getattribute__(x)
                            if num is not None:
                                if x in ["fi", "f"]:
                                    num = num[0]
                                dat_propiedad.append(num._data)
                            else:
                                dat_propiedad.append(None)
                        data["sublimation"][x] = dat_propiedad

        # Define the saturation temperature
        T = list(concatenate([linspace(fluid.Tt, 0.9*fluid.Tc, points),
                              linspace(0.9*fluid.Tc, 0.99*fluid.Tc, points),
                              linspace(0.99*fluid.Tc, fluid.Tc, points)]))
        for i in range(2, 0, -1):
            del T[points*i]

        # Calculate saturation
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating Liquid-Vapour saturation line..."))
        for fase in [0, 1]:
            fluidos = []
            for Ti in T:
                fluidos.append(fluid._new(T=Ti, x=fase))
                self.parent().progressBar.setValue(
                    10+5*fase+5*len(fluidos)/len(T))
                QtWidgets.QApplication.processEvents()

            data["saturation_%i" % fase] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                data["saturation_%i" % fase][key] = dat_propiedad

        # Calculate isoquality lines
        data["x"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isoquality lines..."))
        values = self.LineList("Isoquality", config.Preferences)
        for i, value in enumerate(values):
            fluidos = calcIsoline(fluid, self.config,
                                  "T", "x", T, value, 20, i, 20,
                                  len(values), self.parent().progressBar)

            data["x"][value] = {}
            for x in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["x"][value][x] = dat_propiedad

        # Get limit equation
        if method == "MEOS":
            eq = fluid.eq[self.parent().currentConfig.getint("MEoS", "eq")]
            Tmin = eq["Tmin"]
            Tmax = eq["Tmax"]

            Tt = eq.get("Tt", fluid.Tt)
            if Tmin > Tt:
                Lt = fluid(T=Tmin, x=0)
            else:
                Lt = fluid(T=Tt, x=0)
            Pmin = Lt.P

            Pmax = eq["Pmax"]*1000
        elif method == "COOLPROP":
            Tmin = fluid.eq["Tmin"]
            Tmax = fluid.eq["Tmax"]
            Pmin = fluid.eq["Pmin"]
            Pmax = fluid.eq["Pmax"]
        elif method == "REFPROP":
            pass

        T = list(concatenate(
            [linspace(Tmin, 0.9*fluid.Tc, points),
             linspace(0.9*fluid.Tc, 0.99*fluid.Tc, points),
             linspace(0.99*fluid.Tc, fluid.Tc, points),
             linspace(fluid.Tc, 1.01*fluid.Tc, points),
             linspace(1.01*fluid.Tc, 1.1*fluid.Tc, points),
             linspace(1.1*fluid.Tc, Tmax, points)]))
        P = list(concatenate(
            [logspace(log10(Pmin), log10(0.9*fluid.Pc), points),
             linspace(0.9*fluid.Pc, 0.99*fluid.Pc, points),
             linspace(0.99*fluid.Pc, fluid.Pc, points),
             linspace(fluid.Pc, 1.01*fluid.Pc, points),
             linspace(1.01*fluid.Pc, 1.1*fluid.Pc, points),
             logspace(log10(1.1*fluid.Pc), log10(Pmax), points)]))
        for i in range(5, 0, -1):
            del T[points*i]
            del P[points*i]

        # Calculate isotherm lines
        data["T"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isotherm lines..."))
        values = self.LineList("Isotherm", config.Preferences, fluid)
        for i, value in enumerate(values):
            fluidos = calcIsoline(fluid, self.config,
                                  "P", "T", P, value, 40, i, 10,
                                  len(values), self.parent().progressBar)
            data["T"][value] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["T"][value][key] = dat_propiedad

        # Calculate isobar lines
        data["P"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isobar lines..."))
        values = self.LineList("Isobar", config.Preferences, fluid)
        for i, value in enumerate(values):
            fluidos = calcIsoline(fluid, self.config,
                                  "T", "P", T, value, 50, i, 10,
                                  len(values), self.parent().progressBar)
            data["P"][value] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["P"][value][key] = dat_propiedad

        # Calculate isochor lines
        data["v"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isochor lines..."))
        values = self.LineList("Isochor", config.Preferences, fluid)
        for i, value in enumerate(values):
            fluidos = calcIsoline(fluid, self.config,
                                  "T", "v", T, value, 60, i, 10,
                                  len(values), self.parent().progressBar)
            data["v"][value] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["v"][value][key] = dat_propiedad

        # Calculate isoenthalpic lines
        data["h"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isoenthalpic lines..."))
        vals = self.LineList("Isoenthalpic", config.Preferences, fluid)
        for i, value in enumerate(vals):
            fluidos = calcIsoline(fluid, self.config,
                                  "P", "h", P, value, 70, i, 10,
                                  len(values), self.parent().progressBar)
            data["h"][value] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["h"][value][key] = dat_propiedad

        # Calculate isoentropic lines
        data["s"] = {}
        self.parent().statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Calculating isoentropic lines..."))
        values = self.LineList("Isoentropic", config.Preferences, fluid)
        for i, value in enumerate(values):
            fluidos = calcIsoline(fluid, self.config,
                                  "P", "s", P, value, 80, i, 20,
                                  len(values), self.parent().progressBar)
            data["s"][value] = {}
            for key in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    if fluido is not None and fluido.status:
                        p = fluido.__getattribute__(key)
                        if key in ["fi", "f"]:
                            p = p[0]
                        dat_propiedad.append(p)
                    else:
                        dat_propiedad.append(None)
                data["s"][value][key] = dat_propiedad

        return data

    @staticmethod
    def LineList(name, Preferences, fluid=None):
        """Return a list with the values of isoline name to plot"""
        if Preferences.getboolean("MEOS", name+"Custom"):
            t = []
            for i in Preferences.get("MEOS", name+'List').split(','):
                if i:
                    t.append(float(i))
        else:
            start = Preferences.getfloat("MEOS", name+"Start")
            end = Preferences.getfloat("MEOS", name+"End")
            step = Preferences.getfloat("MEOS", name+"Step")
            t = list(arange(start, end+step, step))

        if fluid is not None and Preferences.getboolean("MEOS", name+"Critic"):
            if name == "Isotherm":
                t.append(fluid.Tc)
            elif name == "Isobar":
                t.append(fluid.Pc)
            elif name == "Isochor":
                t.append(1./fluid.rhoc)
            else:
                prop = {"Isoenthalpic": "h",
                        "Isoentropic": "s"}
                fc = fluid._new(T=fluid.Tc, rho=fluid.rhoc)
                t.append(fc.__getattribute__(prop[name]))
        return t


# Plugin to import in mainwindow, it implement all meos functionality as QMenu
class Menu(QtWidgets.QMenu, plugin):
    """QMenu to import in mainwindow with all meos addon functionality"""
    def __init__(self, parent=None):
        title = QtWidgets.QApplication.translate("pychemqt", "MEoS properties")
        super(Menu, self).__init__(title, parent)
        self.setIcon(QtGui.QIcon(
            os.path.join(config.IMAGE_PATH, "button", "tables.png")))
        self.aboutToShow.connect(self.aboutToShow_menu)

    def aboutToShow_menu(self):
        """Populate menu, check if fluid and reference state are defined to
        enable/disable calculation/plot option"""
        self.clear()
        self.config = self.parent().currentConfig

        fTxt, refTxt, propTxt, confTxt = self._txt()
        flAction = createAction(fTxt, slot=self.showChooseFluid, parent=self)
        refAction = createAction(refTxt, slot=self.showReference, parent=self)
        pAction = createAction(propTxt, slot=self.showProperties, parent=self)
        confAction = createAction(confTxt, slot=self.configure, parent=self)
        menuCalculate = self._menuCalculate()
        menuPlot = self._menuPlot()
        self.addAction(flAction)
        self.addAction(refAction)
        self.addAction(pAction)
        self.addAction(confAction)
        self.addSeparator()
        self.addAction(menuCalculate.menuAction())
        self.addAction(menuPlot.menuAction())
        self.addSeparator()

        # Disable calculation action if fluid and reference are not defined
        if not (self.config.has_option("MEoS", "fluid") and
                self.config.has_option("MEoS", "reference")):
            menuCalculate.setEnabled(False)
            menuPlot.setEnabled(False)


# Dialog with all meos functionality, to associate to a button in tools toolbar
class Dialog(QtWidgets.QDialog, plugin):
    """Dialog to choose fluid for meos plugins calculations"""
    def __init__(self, config=None, parent=None):
        super(Dialog, self).__init__(parent)
        if config is None:
            config = parent.currentConfig
        self.config = config
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Choose fluid"))
        layout = QtWidgets.QGridLayout(self)

        fTxt, refTxt, propTxt, confTxt = self._txt()
        fluid = QtWidgets.QPushButton(fTxt)
        fluid.clicked.connect(self.showChooseFluid)
        layout.addWidget(fluid, 1, 1)
        ref = QtWidgets.QPushButton(refTxt)
        ref.clicked.connect(self.showReference)
        layout.addWidget(ref, 2, 1)
        prop = QtWidgets.QPushButton(propTxt)
        prop.clicked.connect(self.showProperties)
        layout.addWidget(prop, 3, 1)
        conf = QtWidgets.QPushButton(confTxt)
        conf.clicked.connect(self.configure)
        layout.addWidget(conf, 4, 1)

        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed), 5, 1)
        menuCalculate = self._menuCalculate()
        calculate = QtWidgets.QPushButton(menuCalculate.title())
        calculate.setMenu(menuCalculate)
        layout.addWidget(calculate, 6, 1)
        menuPlot = self._menuPlot()
        plot = QtWidgets.QPushButton(menuPlot.title())
        plot.setMenu(menuPlot)
        layout.addWidget(plot, 6, 2)

        # Disable calculation action if fluid and reference are not defined
        if not (self.config.has_option("MEoS", "fluid") and
                self.config.has_option("MEoS", "reference")):
            calculate.setEnabled(False)
            plot.setEnabled(False)

        layout.addItem(QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding), 7, 1, 1, 3)
        btBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btBox.clicked.connect(self.reject)
        layout.addWidget(btBox, 8, 1, 1, 3)


# Dialogs for configuration:
class Ui_ChooseFluid(QtWidgets.QDialog):
    """Dialog to choose fluid for meos plugins calculations"""
    all = True
    group = None

    def __init__(self, config=None, parent=None):
        """config: instance with project config to set initial values"""
        super(Ui_ChooseFluid, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Choose fluid"))
        layout = QtWidgets.QGridLayout(self)

        self.lista = QtWidgets.QListWidget()
        self.fill(mEoS.__all__)
        self.lista.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.lista, 1, 1, 5, 1)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Vertical)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.helpRequested.connect(self.info)
        layout.addWidget(self.buttonBox, 1, 2)

        self.widget = QtWidgets.QWidget(self)
        self.widget.setVisible(False)
        layout.addWidget(self.widget, 6, 1, 1, 2)
        gridLayout = QtWidgets.QGridLayout(self.widget)
        self.radioMEoS = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate("pychemqt", "Use MEoS equation"))
        self.radioMEoS.setChecked(True)
        gridLayout.addWidget(self.radioMEoS, 1, 1, 1, 2)
        gridLayout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Equation")+": "), 2, 1)
        self.eq = QtWidgets.QComboBox()
        gridLayout.addWidget(self.eq, 2, 2)
        self.generalized = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate(
                "pychemqt", "Use generalizated expression"))
        gridLayout.addWidget(self.generalized, 3, 1, 1, 2)
        self.radioPR = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "Use Peng-Robinson cubic equation"))
        gridLayout.addWidget(self.radioPR, 4, 1, 1, 2)

        gridLayout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed),
            5, 1)
        gridLayout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Viscosity")), 6, 1)
        self.visco = QtWidgets.QComboBox()
        gridLayout.addWidget(self.visco, 6, 2)
        gridLayout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Thermal")), 7, 1)
        self.thermal = QtWidgets.QComboBox()
        gridLayout.addWidget(self.thermal, 7, 2)
        gridLayout.addItem(QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Maximum), 8, 2)

        botonFilter = QtWidgets.QPushButton(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] +
            os.path.join("images", "button", "filter.png"))),
            QtWidgets.QApplication.translate("pychemqt", "Filter"))
        botonFilter.clicked.connect(self.filter)
        layout.addWidget(botonFilter, 3, 2, 1, 1)
        botonInfo = QtWidgets.QPushButton(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] +
            os.path.join("images", "button", "helpAbout.png"))),
            QtWidgets.QApplication.translate("pychemqt", "Info"))
        botonInfo.clicked.connect(self.info)
        layout.addWidget(botonInfo, 4, 2, 1, 1)
        self.botonMore = QtWidgets.QPushButton(
            QtWidgets.QApplication.translate("pychemqt", "More..."))
        self.botonMore.setCheckable(True)
        self.botonMore.clicked.connect(self.widget.setVisible)
        layout.addWidget(self.botonMore, 5, 2, 1, 1)

        self.lista.currentRowChanged.connect(self.update)
        self.radioMEoS.toggled.connect(self.eq.setEnabled)

        if config and config.has_option("MEoS", "fluid"):
            self.lista.setCurrentRow(config.getint("MEoS", "fluid"))
            self.eq.setCurrentIndex(config.getint("MEoS", "eq"))
            self.radioPR.setChecked(config.getboolean("MEoS", "PR"))
            self.generalized.setChecked(
                config.getboolean("MEoS", "Generalized"))
            self.visco.setCurrentIndex(config.getint("MEoS", "visco"))
            self.thermal.setCurrentIndex(config.getint("MEoS", "thermal"))

    def id(self):
        """Return correct id of selected fluid in mEoS.__all__ list"""
        id = self.lista.currentRow()

        # Correct id for hidden classes
        if not self.all:
            hiden = 0
            visible = 0
            for grp, boolean in zip(DialogFilterFluid.classOrder, self.group):
                module = mEoS.__getattribute__(grp)
                if boolean:
                    visible += len(module)
                else:
                    hiden += len(module)

                if visible >= id:
                    break
            # Add the element hidden above the selected one
            id += hiden
        return id

    def fill(self, compounds):
        """Fill list fluid
        compounds: List of MEoS subclasses to show"""
        self.lista.clear()
        for fluido in compounds:
            txt = fluido.name
            if fluido.synonym:
                txt += " ("+fluido.synonym+")"
            self.lista.addItem(txt)

    def filter(self):
        """Show dialog with group compound filter"""
        dlg = DialogFilterFluid(self.all, self.group)
        if dlg.exec_():
            if dlg.showAll.isChecked():
                cmps = mEoS.__all__
                self.all = True
            else:
                self.all = False
                self.group = []
                cmps = []
                for i, key in enumerate(dlg.classOrder):
                    if dlg.groups[i].isChecked():
                        cmps += mEoS.__getattribute__(key)
                        self.group.append(True)
                    else:
                        self.group.append(False)
            self.fill(cmps)

    def info(self):
        """Show info dialog for fluid"""
        dialog = Dialog_InfoFluid(mEoS.__all__[self.lista.currentRow()])
        dialog.exec_()

    def update(self, indice):
        """Update data when selected fluid change"""
        fluido = mEoS.__all__[indice]
        self.eq.clear()
        for eq in fluido.eq:
            self.eq.addItem(eq["__name__"])

        self.visco.clear()
        if fluido._viscosity is not None:
            self.visco.setEnabled(True)
            for eq in fluido._viscosity:
                self.visco.addItem(eq["__name__"])
        else:
            self.visco.addItem(
                QtWidgets.QApplication.translate("pychemqt", "Undefined"))
            self.visco.setEnabled(False)

        self.thermal.clear()
        if fluido._thermal is not None:
            self.thermal.setEnabled(True)
            for eq in fluido._thermal:
                self.thermal.addItem(eq["__name__"])
        else:
            self.thermal.addItem(
                QtWidgets.QApplication.translate("pychemqt", "Undefined"))
            self.thermal.setEnabled(False)


class DialogFilterFluid(QtWidgets.QDialog):
    """Dialog for filter compounds family to show"""
    text = {
        "Nobles": QtWidgets.QApplication.translate("pychemqt", "Noble gases"),
        "Gases": QtWidgets.QApplication.translate("pychemqt", "Gases"),
        "Alkanes": QtWidgets.QApplication.translate("pychemqt", "Alkanes"),
        "Naphthenes": QtWidgets.QApplication.translate(
            "pychemqt", "Naphthenes"),
        "Alkenes": QtWidgets.QApplication.translate("pychemqt", "Alkenes"),
        "Heteroatom": QtWidgets.QApplication.translate(
            "pychemqt", "Heteroatom"),
        "CFCs": QtWidgets.QApplication.translate("pychemqt", "CFCs"),
        "Siloxanes": QtWidgets.QApplication.translate("pychemqt", "Siloxanes"),
        "PseudoCompounds": QtWidgets.QApplication.translate(
            "pychemqt", "Pseudo Compounds")}
    classOrder = ["Nobles", "Gases", "Alkanes", "Naphthenes", "Alkenes",
                  "Heteroatom", "CFCs", "Siloxanes", "PseudoCompounds"]

    def __init__(self, all=True, group=None, parent=None):
        super(DialogFilterFluid, self).__init__(parent)
        self.setWindowTitle(QtWidgets.QApplication.translate(
            "pychemqt", "Filter fluids families to show"))
        layout = QtWidgets.QGridLayout(self)
        self.showAll = QtWidgets.QCheckBox(QtWidgets.QApplication.translate(
            "pychemqt", "Show All"))
        layout.addWidget(self.showAll, 1, 1)

        widget = QtWidgets.QWidget()
        layout.addWidget(widget, 2, 1)
        lyt = QtWidgets.QVBoxLayout(widget)
        self.groups = []
        for name in self.classOrder:
            checkBox = QtWidgets.QCheckBox(self.text[name])
            lyt.addWidget(checkBox)
            self.groups.append(checkBox)

        self.showAll.toggled.connect(widget.setDisabled)

        self.showAll.setChecked(all)
        if group is not None:
            for boolean, checkBox in zip(group, self.groups):
                checkBox.setChecked(boolean)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 3, 1)


class Ui_ReferenceState(QtWidgets.QDialog):
    """Dialog for select reference state"""
    def __init__(self, config=None, parent=None):
        """config: instance with project config to set initial values"""
        super(Ui_ReferenceState, self).__init__(parent)
        self.setWindowTitle(QtWidgets.QApplication.translate(
            "pychemqt", "Select reference state"))
        layout = QtWidgets.QGridLayout(self)
        self.OTO = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "OTO,  h,s=0 at 298K and 1 atm"))
        layout.addWidget(self.OTO, 0, 1, 1, 7)
        self.NBP = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "NBP,  h,s=0 saturated liquid at Tb"))
        layout.addWidget(self.NBP, 1, 1, 1, 7)
        self.IIR = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "IIR,  h=200,s=1 saturated liquid at 273K"))
        layout.addWidget(self.IIR, 2, 1, 1, 7)
        self.ASHRAE = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "ASHRAE,  h,s=0 saturated liquid at 243K"))
        layout.addWidget(self.ASHRAE, 3, 1, 1, 7)
        self.personalizado = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate("pychemqt", "Custom"))
        self.personalizado.toggled.connect(self.setEnabled)
        layout.addWidget(self.personalizado, 4, 1, 1, 7)

        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed),
            5, 1)
        layout.addWidget(QtWidgets.QLabel("T:"), 5, 2)
        self.T = Entrada_con_unidades(unidades.Temperature, value=298.15)
        layout.addWidget(self.T, 5, 3)
        layout.addWidget(QtWidgets.QLabel("P:"), 6, 2)
        self.P = Entrada_con_unidades(unidades.Pressure, value=101325)
        layout.addWidget(self.P, 6, 3)
        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed), 5, 4, 2, 1)
        layout.addWidget(QtWidgets.QLabel("h:"), 5, 5)
        self.h = Entrada_con_unidades(unidades.Enthalpy, value=0)
        layout.addWidget(self.h, 5, 6)
        layout.addWidget(QtWidgets.QLabel("s:"), 6, 5)
        self.s = Entrada_con_unidades(unidades.SpecificHeat, value=0)
        layout.addWidget(self.s, 6, 6)
        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding), 7, 7)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 8, 1, 1, 7)

        if config and config.has_option("MEoS", "reference"):
            self.setEnabled(False)
            if config.get("MEoS", "reference") == "OTO":
                self.OTO.setChecked(True)
            elif config.get("MEoS", "reference") == "NBP":
                self.NBP.setChecked(True)
            elif config.get("MEoS", "reference") == "IIR":
                self.IIR.setChecked(True)
            elif config.get("MEoS", "reference") == "ASHRAE":
                self.ASHRAE.setChecked(True)
            else:
                self.personalizado.setChecked(True)
                self.setEnabled(True)
                self.T.setValue(config.getfloat("MEoS", "T"))
                self.P.setValue(config.getfloat("MEoS", "P"))
                self.h.setValue(config.getfloat("MEoS", "h"))
                self.s.setValue(config.getfloat("MEoS", "s"))
        else:
            self.OTO.setChecked(True)
            self.setEnabled(False)

    def setEnabled(self, bool):
        """Enable custom entriees"""
        self.T.setEnabled(bool)
        self.P.setEnabled(bool)
        self.h.setEnabled(bool)
        self.s.setEnabled(bool)


class Dialog_InfoFluid(QtWidgets.QDialog):
    """Dialog to show parameter of element with meos"""
    def __init__(self, element, parent=None):
        """element: class of element to show info"""
        super(Dialog_InfoFluid, self).__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        self.element = element

        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Name")+":"), 1, 1)
        self.name = QtWidgets.QLabel()
        layout.addWidget(self.name, 1, 2)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "R name")+":"), 2, 1)
        self.r_name = QtWidgets.QLabel()
        layout.addWidget(self.r_name, 2, 2)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Formula")+":"), 3, 1)
        self.formula = QtWidgets.QLabel()
        layout.addWidget(self.formula, 3, 2)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "CAS number")+":"), 4, 1)
        self.CAS = QtWidgets.QLabel()
        layout.addWidget(self.CAS, 4, 2)
        layout.addItem(QtWidgets.QSpacerItem(
            30, 30, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding), 1, 3, 3, 1)

        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "M")+":"), 1, 4)
        self.M = Entrada_con_unidades(
            float, textounidad="g/mol", readOnly=True)
        layout.addWidget(self.M, 1, 5)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Tc")+":"), 2, 4)
        self.Tc = Entrada_con_unidades(unidades.Temperature, readOnly=True)
        layout.addWidget(self.Tc, 2, 5)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Pc")+":"), 3, 4)
        self.Pc = Entrada_con_unidades(unidades.Pressure, readOnly=True)
        layout.addWidget(self.Pc, 3, 5)
        layout.addWidget(QtWidgets.QLabel("ρc"+":"), 4, 4)
        self.rhoc = Entrada_con_unidades(
            unidades.Density, "DenGas", readOnly=True)
        layout.addWidget(self.rhoc, 4, 5)
        layout.addItem(QtWidgets.QSpacerItem(
            30, 30, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding), 1, 6, 3, 1)

        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "T triple")+":"), 1, 7)
        self.Tt = Entrada_con_unidades(unidades.Temperature, readOnly=True)
        layout.addWidget(self.Tt, 1, 8)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "T boiling")+":"), 2, 7)
        self.Tb = Entrada_con_unidades(unidades.Temperature, readOnly=True)
        layout.addWidget(self.Tb, 2, 8)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Dipole moment")+":"), 3, 7)
        self.momento = Entrada_con_unidades(
            unidades.DipoleMoment, readOnly=True)
        layout.addWidget(self.momento, 3, 8)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "F acentric")+":"), 4, 7)
        self.f_acent = Entrada_con_unidades(float, readOnly=True)
        layout.addWidget(self.f_acent, 4, 8)

        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed),
            5, 1)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Equation")+": "), 6, 1)
        self.eq = QtWidgets.QComboBox()
        layout.addWidget(self.eq, 6, 2, 1, 7)
        self.stacked = QtWidgets.QStackedWidget()
        layout.addWidget(self.stacked, 7, 1, 1, 8)
        self.eq.currentIndexChanged.connect(self.stacked.setCurrentIndex)

        self.moreButton = QtWidgets.QPushButton(
            QtWidgets.QApplication.translate("pychemqt", "Others"))
        self.moreButton.clicked.connect(self.more)
        layout.addWidget(self.moreButton, 9, 1)
        btBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btBox.clicked.connect(self.reject)
        layout.addWidget(btBox, 9, 2, 1, 7)

        self.fill(element)

    def fill(self, element):
        """Fill values"""
        self.name.setText(element.name)
        self.r_name.setText(element.synonym)
        self.formula.setText(element.formula)
        self.CAS.setText(element.CASNumber)
        self.M.setValue(element.M)
        self.Tc.setValue(element.Tc)
        self.Pc.setValue(element.Pc)
        self.rhoc.setValue(element.rhoc)
        self.Tb.setValue(element.Tb)
        self.Tt.setValue(element.Tt)
        self.momento.setValue(element.momentoDipolar)
        self.f_acent.setValue(element.f_acent)

        for eq in element.eq:
            widget = Widget_MEoS_Data(eq)
            self.stacked.addWidget(widget)
            self.eq.addItem(eq["__name__"])

    def more(self):
        """Show parameter for transport and ancillary equations"""
        dialog = transportDialog(self.element, parent=self)
        dialog.show()


class Widget_MEoS_Data(QtWidgets.QWidget):
    """Widget to show meos data"""
    def __init__(self, eq, parent=None):
        """eq: dict with equation parameter"""
        super(Widget_MEoS_Data, self).__init__(parent)
        gridLayout = QtWidgets.QGridLayout(self)
        txt = " ".join((eq["__doi__"]["autor"], eq["__doi__"]["title"],
                        eq["__doi__"]["ref"]))
        ref = QtWidgets.QLabel(txt)
        ref.setWordWrap(True)
        gridLayout.addWidget(ref, 1, 1)

        tabWidget = QtWidgets.QTabWidget()
        gridLayout.addWidget(tabWidget, 3, 1)

        # Cp tab
        if "ao_log" in eq["cp"]:
            # Cp0 form
            tab1 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab1, QtWidgets.QApplication.translate("pychemqt", "Phi0"))
            gridLayout_Ideal = QtWidgets.QGridLayout(tab1)
            mathTex = r"$\alpha^o=\ln\delta + c_o\ln\tau + \sum c_i\tau^{n_i} "
            mathTex += r"+ \sum_j m_j \ln (1-e^{-\theta_j\tau}) + "
            mathTex += r"\sum_k l_k\ln|\sinh(\psi_k\tau)| - "
            mathTex += r"\sum l_k\ln|\cosh(\psi_k\tau)|$"
            label = QLabelMath(mathTex)
            gridLayout_Ideal.addWidget(label, 1, 1, 1, 3)
            self.Tabla_Cp_poly = Tabla(
                2, horizontalHeader=["n", "d"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_poly, 2, 1)
            self.Tabla_Cp_exp = Tabla(
                2, horizontalHeader=["m", "θ"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_exp, 2, 2)
            self.Tabla_Cp_hyp = Tabla(
                2, horizontalHeader=["l", "ψ"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_hyp, 2, 3)

        else:
            # Phi0 form
            tab1 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab1, QtWidgets.QApplication.translate("pychemqt", "Cp"))
            gridLayout_Ideal = QtWidgets.QGridLayout(tab1)
            mathTex = r"$\frac{C_p^o}{R}=\sum n_i\tau^{d_i}+"
            mathTex += r"\sum m_j(\theta_j\tau)^2\frac{e^{\theta_j\tau}}"
            mathTex += r"{(e^{\theta_j\tau}-1)^2}"
            mathTex += r"+\sum l_k\left(\frac{\phi_k\tau}"
            mathTex += r"{\sinh(\phi_k\tau)}\right)^2"
            mathTex += r"+\sum l_k\left(\frac{\phi_k\tau}"
            mathTex += r"{\cosh(\phi_k\tau)}\right)^2$"
            label = QLabelMath(mathTex)
            gridLayout_Ideal.addWidget(label, 1, 1, 1, 3)
            self.Tabla_Cp_poly = Tabla(
                2, horizontalHeader=["n", "d"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_poly, 2, 1)
            self.Tabla_Cp_exp = Tabla(
                2, horizontalHeader=["m", "θ"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_exp, 2, 2)
            self.Tabla_Cp_hyp = Tabla(
                2, horizontalHeader=["l", "ψ"], stretch=False, readOnly=True)
            gridLayout_Ideal.addWidget(self.Tabla_Cp_hyp, 2, 3)

        if eq["__type__"] == "Helmholtz":
            mathTex = r"$\alpha = \alpha^o+\alpha_{Pol}^r+\alpha_{Exp}^r+"
            mathTex += r"\alpha_{GBS}^r+\alpha_{NA}^r+\alpha_{HE}^r$"
            label = QLabelMath(mathTex)
            gridLayout.addWidget(label, 2, 1)

            # Polinomial tab
            tab2 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab2,
                QtWidgets.QApplication.translate("pychemqt", "Polinomial"))
            gridLayout_pol = QtWidgets.QGridLayout(tab2)
            mathTex = r"$\alpha_{Pol}^r=\sum_i n_i\tau^{t_i}\delta^{d_i}$"
            label = QLabelMath(mathTex)
            gridLayout_pol.addWidget(label, 1, 1)
            self.Tabla_lineal = Tabla(
                3, horizontalHeader=["n", "t", "d"], stretch=False,
                readOnly=True)
            gridLayout_pol.addWidget(self.Tabla_lineal, 2, 1)

            # Exponencial tab
            tab3 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab3,
                QtWidgets.QApplication.translate("pychemqt", "Exponential"))
            gridLayout_Exp = QtWidgets.QGridLayout(tab3)
            mathTex = r"$\alpha_{Exp}^r=\sum_i n_i\tau^{t_i}\delta^{d_i}"
            mathTex += r"e^{-\gamma_i\delta^{c_i}}$"
            label = QLabelMath(mathTex)
            gridLayout_Exp.addWidget(label, 1, 1)
            self.Tabla_exponential = Tabla(
                5, horizontalHeader=["n", "t", "d", "γ", "c"],
                stretch=False, readOnly=True)
            gridLayout_Exp.addWidget(self.Tabla_exponential, 2, 1)

            # Gaussian tab
            tab4 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab4, QtWidgets.QApplication.translate("pychemqt", "Gaussian"))
            gridLayout_gauss = QtWidgets.QGridLayout(tab4)
            mathTex = r"$\alpha_{GBS}^r=\sum_i n_i\tau^{t_i}\delta^{d_i}"
            mathTex += r"e^{-\alpha_i\left(\delta-\epsilon_i\right)^2"
            mathTex += r"-\beta\left(\tau-\gamma_i\right)^2}$"
            label = QLabelMath(mathTex)
            gridLayout_gauss.addWidget(label, 1, 1)
            self.Tabla_gauss = Tabla(
                7, horizontalHeader=["n", "t", "d", "η", "ε", "β", "γ"],
                stretch=False, readOnly=True)
            gridLayout_gauss.addWidget(self.Tabla_gauss, 2, 1)

            # Non analytic tab
            tab5 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab5,
                QtWidgets.QApplication.translate("pychemqt", "Non analytic"))
            gridLayout_NA = QtWidgets.QGridLayout(tab5)
            mathTex = r"$\alpha_{NA}^r=\sum_i n_i\delta\Delta^{b_i}"
            mathTex += r"e^{-C_i\left(\delta-1\right)^2-D_i"
            mathTex += r"\left(\tau-1\right)^2}$"
            label = QLabelMath(mathTex)
            gridLayout_NA.addWidget(label, 1, 1)
            mathTex = r"$\Delta = \left(1-\tau+A_i\left(\left(\delta-1\right)"
            mathTex += r"^2\right)^{1/2\beta_i}\right)^2+B_i\left(\left(\delta"
            mathTex += r"-1\right)^2\right)^{a_i}$"
            label2 = QLabelMath(mathTex)
            gridLayout_NA.addWidget(label2, 2, 1)
            self.Tabla_noanalytic = Tabla(
                8, horizontalHeader=["n", "a", "b", "A", "B", "C", "D", "β"],
                stretch=False, readOnly=True)
            gridLayout_NA.addWidget(self.Tabla_noanalytic, 3, 1)

            # Hard Sphere tab
            tab6 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab6,
                QtWidgets.QApplication.translate("pychemqt", "Hard Sphere"))
            gridLayout_HE = QtWidgets.QGridLayout(tab6)
            mathTex = r"$\alpha_{HE}^r=(\varphi^2-1)\ln(1-\xi)+\frac"
            mathTex += r"{(\varphi^2+3\varphi)\xi-3\varphi\xi^2}{(1-\xi)^2}$"
            label = QLabelMath(mathTex)
            gridLayout_HE.addWidget(label, 1, 1, 1, 2)
            gridLayout_HE.addWidget(QtWidgets.QLabel("φ:"), 2, 1)
            self.fi = Entrada_con_unidades(float, readOnly=True)
            gridLayout_HE.addWidget(self.fi, 2, 2)
            gridLayout_HE.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 3, 1, 1, 2)

        elif eq["__type__"] == "MBWR":
            # Pestaña MBWR
            tab2 = QtWidgets.QWidget()
            tabWidget.addTab(
                tab2, QtWidgets.QApplication.translate("pychemqt", "MBWR"))
            gridLayout_MBWR = QtWidgets.QGridLayout(tab2)
            mathTex = r"$P=\rho RT+\sum_{n=2}^{9}\alpha_n\rho^n + "
            mathTex += r"e^{-\delta^2} \sum_{10}^{15} \alpha_n"
            mathTex += r"\rho^{2n-17}$"
            label = QLabelMath(mathTex)
            gridLayout_MBWR.addWidget(label, 1, 1)
            self.Tabla_MBWR = Tabla(
                1, horizontalHeader=["b"], stretch=False, readOnly=True)
            gridLayout_MBWR.addWidget(self.Tabla_MBWR, 2, 1)

        self.fill(eq)

    def fill(self, eq):
        format = {"format": 1, "total": 5}

        if "ao_log" in eq["cp"]:
            # Phi_o term
            self.Tabla_Cp_poly.setColumn(
                0, eq["cp"]["ao_pow"], **format)
            self.Tabla_Cp_poly.setColumn(1, eq["cp"]["pow"], **format)
            self.Tabla_Cp_poly.resizeColumnsToContents()
            if "ao_exp" in eq["cp"]:
                self.Tabla_Cp_exp.setColumn(0, eq["cp"]["ao_exp"], **format)
                self.Tabla_Cp_exp.setColumn(1, eq["cp"]["titao"], **format)
                self.Tabla_Cp_exp.resizeColumnsToContents()
            if "hyp" in eq["cp"]:
                self.Tabla_Cp_hyp.setColumn(0, eq["cp"]["ao_hyp"], **format)
                self.Tabla_Cp_hyp.setColumn(1, eq["cp"]["hyp"], **format)
                self.Tabla_Cp_hyp.resizeColumnsToContents()
        else:
            # Cp term
            an = eq["cp"].get("an", [])
            t = eq["cp"].get("pow", [])
            ao = eq["cp"].get("ao", 0)
            if ao:
                an.insert(0, ao)
                t.insert(0, 0)

            if an:
                self.Tabla_Cp_poly.setColumn(0, an, **format)
                self.Tabla_Cp_poly.setColumn(1, t, **format)
                self.Tabla_Cp_poly.resizeColumnsToContents()

            if "ao_exp" in eq["cp"]:
                self.Tabla_Cp_exp.setColumn(0, eq["cp"]["ao_exp"], **format)
                self.Tabla_Cp_exp.setColumn(1, eq["cp"]["exp"], **format)
                self.Tabla_Cp_exp.resizeColumnsToContents()

            if "hyp" in eq["cp"]:
                self.Tabla_Cp_hyp.setColumn(0, eq["cp"]["ao_hyp"], **format)
                self.Tabla_Cp_hyp.setColumn(1, eq["cp"]["hyp"], **format)
                self.Tabla_Cp_hyp.resizeColumnsToContents()

        if eq["__type__"] == "Helmholtz":
            if eq.get("nr1", []):
                self.Tabla_lineal.setColumn(0, eq["nr1"], **format)
                self.Tabla_lineal.setColumn(1, eq["t1"], **format)
                self.Tabla_lineal.setColumn(2, eq["d1"], **format)
            if eq.get("nr2", []):
                self.Tabla_exponential.setColumn(0, eq["nr2"], **format)
                self.Tabla_exponential.setColumn(1, eq["t2"], **format)
                self.Tabla_exponential.setColumn(2, eq["d2"], **format)
                self.Tabla_exponential.setColumn(3, eq["gamma2"], **format)
                self.Tabla_exponential.setColumn(4, eq["c2"], **format)
            if eq.get("nr3", []):
                self.Tabla_gauss.setColumn(0, eq["nr3"], **format)
                self.Tabla_gauss.setColumn(1, eq["t3"], **format)
                self.Tabla_gauss.setColumn(2, eq["d3"], **format)
                self.Tabla_gauss.setColumn(3, eq["alfa3"], **format)
                self.Tabla_gauss.setColumn(4, eq["beta3"], **format)
                self.Tabla_gauss.setColumn(5, eq["gamma3"], **format)
                self.Tabla_gauss.setColumn(6, eq["epsilon3"], **format)
            if eq.get("nr4", []):
                self.Tabla_noanalytic.setColumn(0, eq["nr4"], **format)
                self.Tabla_noanalytic.setColumn(1, eq["a4"], **format)
                self.Tabla_noanalytic.setColumn(2, eq["b4"], **format)
                self.Tabla_noanalytic.setColumn(3, eq["A"], **format)
                self.Tabla_noanalytic.setColumn(4, eq["B"], **format)
                self.Tabla_noanalytic.setColumn(5, eq["C"], **format)
                self.Tabla_noanalytic.setColumn(6, eq["D"], **format)
                self.Tabla_noanalytic.setColumn(7, eq["beta4"], **format)
            self.Tabla_lineal.resizeColumnsToContents()
            self.Tabla_exponential.resizeColumnsToContents()
            self.Tabla_gauss.resizeColumnsToContents()
            self.Tabla_noanalytic.resizeColumnsToContents()

        elif eq["__type__"] == "MBWR":
            self.Tabla_MBWR.setColumn(0, eq["b"][1:], **format)
            self.Tabla_MBWR.resizeColumnsToContents()


class transportDialog(QtWidgets.QDialog):
    """Dialog to show parameters for transport and ancillary equations"""
    def __init__(self, element, parent=None):
        super(transportDialog, self).__init__(parent)
        gridLayout = QtWidgets.QGridLayout(self)
        self.element = element

        tabWidget = QtWidgets.QTabWidget()
        gridLayout.addWidget(tabWidget, 1, 1)

        # Tab viscosity
        tab3 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab3, QtWidgets.QApplication.translate("pychemqt", "Viscosity"))
        gridLayout_viscosity = QtWidgets.QGridLayout(tab3)

        gridLayout_viscosity.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate(
                "pychemqt", "Equation")+": "), 1, 1)
        self.eqVisco = QtWidgets.QComboBox()
        gridLayout_viscosity.addWidget(self.eqVisco, 1, 2)
        gridLayout_viscosity.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed), 1, 3)
        self.stackedVisco = QtWidgets.QStackedWidget()
        gridLayout_viscosity.addWidget(self.stackedVisco, 2, 1, 1, 3)
        self.eqVisco.currentIndexChanged.connect(
            self.stackedVisco.setCurrentIndex)

        if element._viscosity is not None:
            for eq in element._viscosity:
                widget = Widget_Viscosity_Data(element, eq)
                self.stackedVisco.addWidget(widget)
                self.eqVisco.addItem(eq["__name__"])
        else:
            self.eqVisco.addItem(QtWidgets.QApplication.translate(
                "pychemqt", "Not Implemented"))

        # Tab thermal conductivity
        tab4 = QtWidgets.QWidget()
        tabWidget.addTab(tab4,
                         QtWidgets.QApplication.translate(
                             "pychemqt", "Thermal Conductivity"))
        gridLayout_conductivity = QtWidgets.QGridLayout(tab4)

        gridLayout_conductivity.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Equation")+": "),
            1, 1)
        self.eqThermo = QtWidgets.QComboBox()
        gridLayout_conductivity.addWidget(self.eqThermo, 1, 2)
        gridLayout_conductivity.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed), 1, 3)
        self.stackedThermo = QtWidgets.QStackedWidget()
        gridLayout_conductivity.addWidget(self.stackedThermo, 2, 1, 1, 3)
        self.eqThermo.currentIndexChanged.connect(
            self.stackedThermo.setCurrentIndex)

        if element._thermal is not None:
            for eq in element._thermal:
                widget = Widget_Conductivity_Data(element, eq)
                self.stackedThermo.addWidget(widget)
                self.eqThermo.addItem(eq["__name__"])
        else:
            self.eqThermo.addItem(QtWidgets.QApplication.translate(
                "pychemqt", "Not Implemented"))

        # Tab dielectric constant
        tab1 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab1, QtWidgets.QApplication.translate("pychemqt", "Dielectric"))
        gridLayout_dielectric = QtWidgets.QGridLayout(tab1)

        if element._Dielectric != meos.MEoS._Dielectric:
            label = QtWidgets.QLabel(element._Dielectric.__doc__)
            label.setWordWrap(True)
            gridLayout_dielectric.addWidget(label, 1, 1)
            self.codigo_Dielectric = SimplePythonEditor()
            self.codigo_Dielectric.setText(
                inspect.getsource(element._Dielectric))
            gridLayout_dielectric.addWidget(self.codigo_Dielectric, 2, 1)
        elif element._dielectric:
            label = QtWidgets.QLabel(element._Dielectric.__doc__)
            label.setWordWrap(True)
            gridLayout_dielectric.addWidget(label, 1, 1)

            self.Table_Dielectric = Tabla(
                1, verticalHeader=True, filas=5, stretch=False, readOnly=True)
            gridLayout_dielectric.addWidget(self.Table_Dielectric, 2, 1)
            i = 0
            for key, valor in element._dielectric.items():
                self.Table_Dielectric.setVerticalHeaderItem(
                    i, QtWidgets.QTableWidgetItem(key))
                self.Table_Dielectric.setItem(
                    0, i, QtWidgets.QTableWidgetItem(str(valor)))
                i += 1
            self.Table_Dielectric.resizeColumnsToContents()
        else:
            gridLayout_dielectric.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_dielectric.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab surface tension
        tab2 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab2,
            QtWidgets.QApplication.translate("pychemqt", "Surface Tension"))
        gridLayout_surface = QtWidgets.QGridLayout(tab2)

        if element._Surface != meos.MEoS._Surface:
            label = QtWidgets.QLabel(element._Surface.__doc__)
            label.setWordWrap(True)
            gridLayout_surface.addWidget(label, 1, 1)
            self.codigo_Surface = SimplePythonEditor()
            self.codigo_Surface.setText(inspect.getsource(element._Surface))
            gridLayout_surface.addWidget(self.codigo_Surface, 2, 1)
        elif element._surface:
            label = QtWidgets.QLabel(element._Surface.__doc__)
            label.setWordWrap(True)
            gridLayout_surface.addWidget(label, 1, 1)

            self.Table_Surface = Tabla(
                2, horizontalHeader=["σ", "n"], verticalHeader=True,
                stretch=False, readOnly=True)
            self.Table_Surface.setColumn(0, element._surface["sigma"])
            self.Table_Surface.setColumn(1, element._surface["exp"])
            gridLayout_surface.addWidget(self.Table_Surface, 2, 1)
            self.Table_Surface.resizeColumnsToContents()
        else:
            gridLayout_surface.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_surface.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab liquid density
        tab5 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab5,
            QtWidgets.QApplication.translate("pychemqt", "Liquid Density"))
        gridLayout_liquid_density = QtWidgets.QGridLayout(tab5)

        if element._Liquid_Density != meos.MEoS._Liquid_Density:
            label = QtWidgets.QLabel(element._Liquid_Density.__doc__)
            label.setWordWrap(True)
            gridLayout_liquid_density.addWidget(label, 1, 1)
            self.codigo_Liquid_Density = SimplePythonEditor()
            self.codigo_Liquid_Density.setText(
                inspect.getsource(element._Liquid_Density))
            gridLayout_liquid_density.addWidget(
                self.codigo_Liquid_Density, 2, 1)
        elif element._liquid_Density:
            label = QtWidgets.QLabel(element._Liquid_Density.__doc__)
            label.setWordWrap(True)
            gridLayout_liquid_density.addWidget(label, 1, 1)

            self.Table_Liquid_Density = Tabla(
                2, horizontalHeader=["n", "t"],
                verticalHeader=True, stretch=False, readOnly=True)
            self.Table_Liquid_Density.setColumn(
                0, element._liquid_Density["n"])
            self.Table_Liquid_Density.setColumn(
                1, element._liquid_Density["t"])
            gridLayout_liquid_density.addWidget(
                self.Table_Liquid_Density, 2, 1)
            self.Table_Liquid_Density.resizeColumnsToContents()
        else:
            gridLayout_liquid_density.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_liquid_density.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab vapor density
        tab6 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab6,
            QtWidgets.QApplication.translate("pychemqt", "Vapor Density"))
        gridLayout_vapor_density = QtWidgets.QGridLayout(tab6)

        if element._Vapor_Density != meos.MEoS._Vapor_Density:
            label = QtWidgets.QLabel(element._Vapor_Density.__doc__)
            label.setWordWrap(True)
            gridLayout_vapor_density.addWidget(label, 1, 1)
            self.codigo_Vapor_Density = SimplePythonEditor()
            self.codigo_Vapor_Density.setText(
                inspect.getsource(element._Vapor_Density))
            gridLayout_vapor_density.addWidget(self.codigo_Vapor_Density, 2, 1)
        elif element._vapor_Density:
            label = QtWidgets.QLabel(element._Vapor_Density.__doc__)
            label.setWordWrap(True)
            gridLayout_vapor_density.addWidget(label, 1, 1)

            self.Table_Vapor_Density = Tabla(
                2, horizontalHeader=["n", "t"], verticalHeader=True,
                stretch=False, readOnly=True)
            self.Table_Vapor_Density.setColumn(0, element._vapor_Density["n"])
            self.Table_Vapor_Density.setColumn(
                1, element._vapor_Density["t"])
            gridLayout_vapor_density.addWidget(self.Table_Vapor_Density, 2, 1)
            self.Table_Vapor_Density.resizeColumnsToContents()
        else:
            gridLayout_vapor_density.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_vapor_density.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab vapor presure
        tab7 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab7,
            QtWidgets.QApplication.translate("pychemqt", "Vapor Pressure"))
        gridLayout_vapor_pressure = QtWidgets.QGridLayout(tab7)

        if element._Vapor_Pressure != meos.MEoS._Vapor_Pressure:
            label = QtWidgets.QLabel(element._Vapor_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout_vapor_pressure.addWidget(label, 1, 1)
            self.codigo_Vapor_Pressure = SimplePythonEditor()
            self.codigo_Vapor_Pressure.setText(
                inspect.getsource(element._Vapor_Pressure))
            gridLayout_vapor_pressure.addWidget(
                self.codigo_Vapor_Pressure, 2, 1)
        elif element._vapor_Pressure:
            label = QtWidgets.QLabel(element._Vapor_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout_vapor_pressure.addWidget(label, 1, 1)

            self.Table_Vapor_Pressure = Tabla(
                2, horizontalHeader=["n", "t"], verticalHeader=True,
                stretch=False, readOnly=True)
            self.Table_Vapor_Pressure.setColumn(
                0, element._vapor_Pressure["n"])
            self.Table_Vapor_Pressure.setColumn(
                1, element._vapor_Pressure["t"])
            gridLayout_vapor_pressure.addWidget(
                self.Table_Vapor_Pressure, 2, 1)
            self.Table_Vapor_Pressure.resizeColumnsToContents()
        else:
            gridLayout_vapor_pressure.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_vapor_pressure.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab melting presure
        tab8 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab8,
            QtWidgets.QApplication.translate("pychemqt", "Melting Pressure"))
        gridLayout_melting_pressure = QtWidgets.QGridLayout(tab8)

        if element._Melting_Pressure != meos.MEoS._Melting_Pressure:
            label = QtWidgets.QLabel(element._Melting_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout_melting_pressure.addWidget(label, 1, 1)
            self.codigo_Melting_Pressure = SimplePythonEditor()
            self.codigo_Melting_Pressure.setText(
                inspect.getsource(element._Melting_Pressure))
            gridLayout_melting_pressure.addWidget(
                self.codigo_Melting_Pressure, 2, 1)
        elif element._melting:
            label = QtWidgets.QLabel(element._Melting_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout_melting_pressure.addWidget(label, 1, 1)

            self.Table_Melting_Pressure = Tabla(
                6, horizontalHeader=["a1", "n1", "a2", "n2", "a3", "n3"],
                verticalHeader=True, stretch=False, readOnly=True)
            self.Table_Melting_Pressure.setColumn(0, element._melting["a1"])
            self.Table_Melting_Pressure.setColumn(1, element._melting["exp1"])
            self.Table_Melting_Pressure.setColumn(2, element._melting["a2"])
            self.Table_Melting_Pressure.setColumn(3, element._melting["exp2"])
            self.Table_Melting_Pressure.setColumn(4, element._melting["a3"])
            self.Table_Melting_Pressure.setColumn(5, element._melting["exp3"])
            gridLayout_melting_pressure.addWidget(
                self.Table_Melting_Pressure, 2, 1)
            self.Table_Melting_Pressure.resizeColumnsToContents()
        else:
            gridLayout_melting_pressure.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout_melting_pressure.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab sublimation presure
        tab9 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab9,
            QtWidgets.QApplication.translate(
                "pychemqt", "Sublimation Pressure"))
        gridLayout__sublimation_pressure = QtWidgets.QGridLayout(tab9)

        if element._Sublimation_Pressure != meos.MEoS._Sublimation_Pressure:
            label = QtWidgets.QLabel(element._Sublimation_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout__sublimation_pressure.addWidget(label, 1, 1)
            self.codigo_Sublimation_Pressure = SimplePythonEditor()
            self.codigo_Sublimation_Pressure.setText(
                inspect.getsource(element._Sublimation_Pressure))
            gridLayout__sublimation_pressure.addWidget(
                self.codigo_Sublimation_Pressure, 2, 1)
        elif element._sublimation:
            label = QtWidgets.QLabel(element._Melting_Pressure.__doc__)
            label.setWordWrap(True)
            gridLayout__sublimation_pressure.addWidget(label, 1, 1)

            self.Table_Sublimation_Pressure = Tabla(
                6, horizontalHeader=["a1", "n1", "a2", "n2", "a3", "n3"],
                verticalHeader=True, stretch=False, readOnly=True)
            self.Table_Sublimation_Pressure.setColumn(
                0, element._sublimation["a1"])
            self.Table_Sublimation_Pressure.setColumn(
                1, element._sublimation["exp1"])
            self.Table_Sublimation_Pressure.setColumn(
                2, element._sublimation["a2"])
            self.Table_Sublimation_Pressure.setColumn(
                3, element._sublimation["exp2"])
            self.Table_Sublimation_Pressure.setColumn(
                4, element._sublimation["a3"])
            self.Table_Sublimation_Pressure.setColumn(
                5, element._sublimation["exp3"])
            gridLayout__sublimation_pressure.addWidget(
                self.Table_Sublimation_Pressure, 2, 1)
            self.Table_Sublimation_Pressure.resizeColumnsToContents()
        else:
            gridLayout__sublimation_pressure.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Not Implemented")), 1, 1)
            gridLayout__sublimation_pressure.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        # Tab Peng-Robinson
        tab10 = QtWidgets.QWidget()
        tabWidget.addTab(
            tab10,
            QtWidgets.QApplication.translate("pychemqt", "Peng-Robinson"))
        gridLayout_PengRobinson = QtWidgets.QGridLayout(tab10)

        if element._PR:
            label = QtWidgets.QLabel(element._PengRobinson.__doc__)
            label.setWordWrap(True)
            gridLayout_PengRobinson.addWidget(label, 1, 1, 1, 3)
            gridLayout_PengRobinson.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Fixed,
                QtWidgets.QSizePolicy.Fixed), 2, 1, 1, 3)
            gridLayout_PengRobinson.addWidget(QtWidgets.QLabel("C"), 3, 1)
            self.PR = Entrada_con_unidades(
                float, decimales=6, value=element._PR, readOnly=True)
            gridLayout_PengRobinson.addWidget(self.PR, 3, 2)
            gridLayout_PengRobinson.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 4, 1, 1, 3)
        else:
            gridLayout_PengRobinson.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "No Peneloux correction")), 1, 1)
            gridLayout_PengRobinson.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 2, 1)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close)
        self.buttonBox.clicked.connect(self.reject)
        gridLayout.addWidget(self.buttonBox, 2, 1)


class Widget_Viscosity_Data(QtWidgets.QWidget):
    """Widget to show viscosity data"""
    def __init__(self, element, eq, parent=None):
        """
        element: element class for code extract
        eq: dict with viscosity parameter"""
        super(Widget_Viscosity_Data, self).__init__(parent)
        gridLayout = QtWidgets.QGridLayout(self)
        if eq["eq"] == 0:
            txt = element.__getattribute__(element, eq["method"]).__doc__
        else:
            txt = " ".join((eq["__doi__"]["autor"], eq["__doi__"]["title"],
                            eq["__doi__"]["ref"]))
        ref = QtWidgets.QLabel(txt)
        ref.setWordWrap(True)
        gridLayout.addWidget(ref, 1, 1, 1, 3)

        if eq["eq"] == 0:
            # Hardcoded method, show code
            self.codigo_Viscosity = SimplePythonEditor()
            code = ""
            for method in eq.get("__code__", ()):
                code += inspect.getsource(method)
                code += os.linesep
            code += inspect.getsource(
                element.__getattribute__(element, eq["method"]))
            self.codigo_Viscosity.setText(code)
            gridLayout.addWidget(self.codigo_Viscosity, 2, 1, 1, 3)
        elif eq["eq"] == 1:
            gridLayout.addWidget(QtWidgets.QLabel("ε/k"), 4, 1)
            self.ek = Entrada_con_unidades(
                float, value=eq["ek"], readOnly=True)
            gridLayout.addWidget(self.ek, 4, 2)
            gridLayout.addWidget(QtWidgets.QLabel("σ"), 5, 1)
            self.sigma = Entrada_con_unidades(
                float, value=eq["sigma"], readOnly=True)
            gridLayout.addWidget(self.sigma, 5, 2)
            tab = QtWidgets.QTabWidget()
            gridLayout.addWidget(tab, 6, 1, 1, 3)

            # Integral collision
            self.Tabla_Collision = Tabla(
                1, horizontalHeader=["b"], stretch=False, readOnly=True)
            if "collision" in eq:
                self.Tabla_Collision.setColumn(0, eq["collision"])
                self.Tabla_Collision.resizeColumnsToContents()
            else:
                self.Tabla_Collision.setDisabled(True)
            tab.addTab(
                self.Tabla_Collision,
                QtWidgets.QApplication.translate("pychemqt", "Collision"))

            # Virial
            self.Tabla_Virial = Tabla(
                2, horizontalHeader=["n", "t"], stretch=False, readOnly=True)
            if "n_virial" in eq:
                self.Tabla_Virial.setColumn(0, eq["n_virial"])
                self.Tabla_Virial.setColumn(1, eq["t_virial"])
                self.Tabla_Virial.resizeColumnsToContents()
            else:
                self.Tabla_Virial.setDisabled(True)
            tab.addTab(self.Tabla_Virial,
                       QtWidgets.QApplication.translate("pychemqt", "Virial"))

            # Close-packed
            self.Tabla_Packed = Tabla(
                2, horizontalHeader=["n", "t"], stretch=False, readOnly=True)
            if "n_packed" in eq:
                self.Tabla_Packed.setColumn(0, eq["n_packed"])
                self.Tabla_Packed.setColumn(1, eq["t_packed"])
                self.Tabla_Packed.resizeColumnsToContents()
            else:
                self.Tabla_Packed.setDisabled(True)
            tab.addTab(self.Tabla_Packed, QtWidgets.QApplication.translate(
                "pychemqt", "Close-packed density"))

            # polynomial term
            self.Tabla_Visco1 = Tabla(
                5, horizontalHeader=["n", "t", "d", "g", "c"], stretch=False,
                readOnly=True)
            if "n_poly" in eq:
                self.Tabla_Visco1.setColumn(0, eq["n_poly"])
                self.Tabla_Visco1.setColumn(1, eq["t_poly"])
                self.Tabla_Visco1.setColumn(2, eq["d_poly"])
                self.Tabla_Visco1.setColumn(3, eq["g_poly"])
                self.Tabla_Visco1.setColumn(4, eq["c_poly"])
                self.Tabla_Visco1.resizeColumnsToContents()
            else:
                self.Tabla_Visco1.setDisabled(True)
            tab.addTab(
                self.Tabla_Visco1,
                QtWidgets.QApplication.translate("pychemqt", "Polinomial"))

            # numerator of rational poly
            self.Tabla_numerator = Tabla(
                5, horizontalHeader=["n", "t", "d", "g", "c"], stretch=False,
                readOnly=True)
            if "n_num" in eq:
                self.Tabla_numerator.setColumn(0, eq["n_num"])
                self.Tabla_numerator.setColumn(1, eq["t_num"])
                self.Tabla_numerator.setColumn(2, eq["d_num"])
                self.Tabla_numerator.setColumn(3, eq["c_num"])
                self.Tabla_numerator.setColumn(4, eq["g_num"])
                self.Tabla_numerator.resizeColumnsToContents()
            else:
                self.Tabla_numerator.setDisabled(True)
            tab.addTab(
                self.Tabla_numerator,
                QtWidgets.QApplication.translate("pychemqt", "Numerator"))

            # denominator of rational poly
            self.Tabla_denominator = Tabla(
                5, horizontalHeader=["n", "t", "d", "g", "c"], stretch=False,
                readOnly=True)
            if "n_den" in eq:
                self.Tabla_denominator.setColumn(0, eq["n_den"])
                self.Tabla_denominator.setColumn(1, eq["t_den"])
                self.Tabla_denominator.setColumn(2, eq["d_den"])
                self.Tabla_denominator.setColumn(3, eq["c_den"])
                self.Tabla_denominator.setColumn(4, eq["g_den"])
                self.Tabla_denominator.resizeColumnsToContents()
            else:
                self.Tabla_denominator.setDisabled(True)
            tab.addTab(
                self.Tabla_denominator,
                QtWidgets.QApplication.translate("pychemqt", "Denominator"))
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 10, 3)

        elif eq["eq"] == 2:
            gridLayout.addWidget(QtWidgets.QLabel("ε/k"), 4, 1)
            self.ek = Entrada_con_unidades(
                float, value=eq["ek"], readOnly=True)
            gridLayout.addWidget(self.ek, 4, 2)
            gridLayout.addWidget(QtWidgets.QLabel("σ"), 5, 1)
            self.sigma = Entrada_con_unidades(
                float, value=eq["sigma"], readOnly=True)
            gridLayout.addWidget(self.sigma, 5, 2)
            self.Tabla_Visco2 = Tabla(
                3, horizontalHeader=["b", "F", "E"], stretch=False,
                readOnly=True)
            if "collision" in eq:
                self.Tabla_Visco2.setColumn(0, eq["collision"])
            self.Tabla_Visco2.setColumn(1, eq["F"])
            self.Tabla_Visco2.setColumn(2, eq["E"])
            self.Tabla_Visco2.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Visco2, 6, 1, 1, 3)
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 10, 3)

        elif eq["eq"] == 3:
            self.Tabla_Visco3 = Tabla(
                8, stretch=False, readOnly=True,
                horizontalHeader=["n-poly", "t-poly", "n-num", "t-num",
                                  "d-num", "n-den", "t-den", "d-den"])
            if "n_poly" in eq:
                self.Tabla_Visco3.setColumn(0, eq["n_poly"])
                self.Tabla_Visco3.setColumn(1, eq["t_poly"])
            if "n_num" in eq:
                self.Tabla_Visco3.setColumn(2, eq["n_num"])
                self.Tabla_Visco3.setColumn(3, eq["t_num"])
                self.Tabla_Visco3.setColumn(4, eq["d_num"])
            if "n_den" in eq:
                self.Tabla_Visco3.setColumn(5, eq["n_den"])
                self.Tabla_Visco3.setColumn(6, eq["t_den"])
                self.Tabla_Visco3.setColumn(7, eq["d_den"])
            self.Tabla_Visco3.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Visco3, 4, 1, 1, 3)
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 10, 3)

        elif eq["eq"] == 4:
            gridLayout.addWidget(QtWidgets.QLabel("ε/k"), 4, 1)
            self.ek = Entrada_con_unidades(
                float, value=eq.get("ek", None), readOnly=True)
            gridLayout.addWidget(self.ek, 4, 2)
            gridLayout.addWidget(QtWidgets.QLabel("σ"), 5, 1)
            self.sigma = Entrada_con_unidades(
                float, value=eq.get("sigma", None), readOnly=True)
            gridLayout.addWidget(self.sigma, 5, 2)
            self.Tabla_Visco4 = Tabla(
                7, stretch=False, readOnly=True,
                horizontalHeader=["a", "b", "c", "A", "B", "C", "D"])
            format = {"format": 1, "decimales": 10}
            self.Tabla_Visco4.setColumn(0, eq["a"], **format)
            self.Tabla_Visco4.setColumn(1, eq["b"], **format)
            self.Tabla_Visco4.setColumn(2, eq["c"], **format)
            self.Tabla_Visco4.setColumn(3, eq["A"], **format)
            self.Tabla_Visco4.setColumn(4, eq["B"], **format)
            self.Tabla_Visco4.setColumn(5, eq["C"], **format)
            # self.Tabla_Visco4.setColumn(6, eq["D"], **format)
            self.Tabla_Visco4.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Visco4, 6, 1, 1, 3)
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 10, 3)

        elif eq["eq"] == 5:
            gridLayout.addWidget(QtWidgets.QLabel("w"), 4, 1)
            self.w = Entrada_con_unidades(float, value=eq["w"], readOnly=True)
            gridLayout.addWidget(self.w, 4, 2)
            gridLayout.addWidget(QtWidgets.QLabel("mur"), 5, 1)
            self.mur = Entrada_con_unidades(
                float, value=eq["mur"], readOnly=True)
            gridLayout.addWidget(self.mur, 5, 2)
            gridLayout.addWidget(QtWidgets.QLabel("ε/k"), 6, 1)
            self.k = Entrada_con_unidades(float, value=eq["k"], readOnly=True)
            gridLayout.addWidget(self.k, 6, 2)
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 10, 3)


class Widget_Conductivity_Data(QtWidgets.QWidget):
    """Widget to show thermal conductivity data"""
    def __init__(self, element, eq, parent=None):
        """
        element: element class for code extract
        eq: dict with thermal conductivity parameter"""
        super(Widget_Conductivity_Data, self).__init__(parent)
        gridLayout = QtWidgets.QGridLayout(self)
        if eq["eq"] == 0:
            txt = element.__getattribute__(element, eq["method"]).__doc__
        else:
            txt = " ".join((eq["__doi__"]["autor"], eq["__doi__"]["title"],
                            eq["__doi__"]["ref"]))
        ref = QtWidgets.QLabel(txt)
        ref.setWordWrap(True)
        gridLayout.addWidget(ref, 1, 1, 1, 3)

        if eq["eq"] == 0:
            # Hardcoded method, show code
            self.code = SimplePythonEditor()
            code = ""
            for method in eq.get("__code__", ()):
                code += inspect.getsource(method)
                code += os.linesep
            code += inspect.getsource(
                element.__getattribute__(element, eq["method"]))
            self.code.setText(code)
            gridLayout.addWidget(self.code, 2, 1, 1, 3)

        elif eq["eq"] == 1:
            self.Tabla_Therm1 = Tabla(
                11, stretch=False, readOnly=True,
                horizontalHeader=["no", "co", "noden", "toden", "nb", "tb",
                                  "db", "cb", "nbden", "tbden", "dbden"])
            if "no" in eq:
                self.Tabla_Therm1.setColumn(0, eq["no"])
                self.Tabla_Therm1.setColumn(1, eq["co"])
            if "noden" in eq:
                self.Tabla_Therm1.setColumn(2, eq["noden"])
                self.Tabla_Therm1.setColumn(3, eq["toden"])
            if "nb" in eq:
                self.Tabla_Therm1.setColumn(4, eq["nb"])
                self.Tabla_Therm1.setColumn(5, eq["tb"])
                self.Tabla_Therm1.setColumn(6, eq["db"])
                self.Tabla_Therm1.setColumn(7, eq["cb"])
            if "nbden" in eq:
                self.Tabla_Therm1.setColumn(8, eq["nbden"])
                self.Tabla_Therm1.setColumn(9, eq["tbden"])
                self.Tabla_Therm1.setColumn(10, eq["dbden"])
            self.Tabla_Therm1.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Therm1, 3, 1, 1, 3)

        elif eq["eq"] == 2:
            self.Tabla_Therm2 = Tabla(
                2, horizontalHeader=["E", "G"], stretch=False, readOnly=True)
            self.Tabla_Therm2.setColumn(0, eq["E"])
            self.Tabla_Therm2.setColumn(1, eq["G"])
            self.Tabla_Therm2.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Therm2, 3, 1, 1, 3)

        elif eq["eq"] == 3:
            self.Tabla_Therm3 = Tabla(
                3, horizontalHeader=["b", "F", "E"],
                stretch=False, readOnly=True)
            self.Tabla_Therm3.setColumn(0, eq["b"])
            self.Tabla_Therm3.setColumn(1, eq["F"])
            self.Tabla_Therm3.setColumn(2, eq["E"])
            self.Tabla_Therm3.resizeColumnsToContents()
            gridLayout.addWidget(self.Tabla_Therm3, 3, 1, 1, 3)

            parameter = QtWidgets.QWidget()
            gridLayout.addWidget(parameter, 4, 1, 1, 3)
            lyt = QtWidgets.QGridLayout(parameter)
            lyt.addWidget(QtWidgets.QLabel("ε/k"), 1, 1)
            self.ek = Entrada_con_unidades(
                float, value=eq["ek"], readOnly=True)
            lyt.addWidget(self.ek, 1, 2)
            lyt.addWidget(QtWidgets.QLabel("σ"), 2, 1)
            self.sigma = Entrada_con_unidades(
                float, value=eq["sigma"], readOnly=True)
            lyt.addWidget(self.sigma, 2, 2)
            lyt.addWidget(QtWidgets.QLabel("Nchapman"), 3, 1)
            self.Nchapman = Entrada_con_unidades(
                float, value=eq["Nchapman"], readOnly=True)
            lyt.addWidget(self.Nchapman, 3, 2)
            lyt.addWidget(QtWidgets.QLabel("tchapman"), 4, 1)
            self.tchapman = Entrada_con_unidades(
                float, value=eq["tchapman"], readOnly=True)
            lyt.addWidget(self.tchapman, 4, 2)
            lyt.addWidget(QtWidgets.QLabel("rhoc"), 1, 4)
            self.rhoc = Entrada_con_unidades(
                float, value=eq["rhoc"], readOnly=True)
            lyt.addWidget(self.rhoc, 1, 5)
            lyt.addWidget(QtWidgets.QLabel("ff"), 2, 4)
            self.ff = Entrada_con_unidades(
                float, value=eq["ff"], readOnly=True)
            lyt.addWidget(self.ff, 2, 5)
            lyt.addWidget(QtWidgets.QLabel("rm"), 3, 4)
            self.rm = Entrada_con_unidades(
                float, value=eq["rm"], readOnly=True)
            lyt.addWidget(self.rm, 3, 5)

        if "critical" in eq and eq["critical"]:
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Fixed,
                QtWidgets.QSizePolicy.Fixed), 5, 3)
            gridLayout.addWidget(QtWidgets.QLabel(
                QtWidgets.QApplication.translate(
                    "pychemqt", "Critical enhancement")), 6, 1, 1, 2)
            if eq["critical"] == 3:
                gridLayout.addWidget(QtWidgets.QLabel("gnu"), 7, 1)
                self.gnu = Entrada_con_unidades(
                    float, value=eq["gnu"], readOnly=True)
                gridLayout.addWidget(self.gnu, 7, 2)
                gridLayout.addWidget(QtWidgets.QLabel("γ"), 8, 1)
                self.gamma = Entrada_con_unidades(
                    float, value=eq["gamma"], readOnly=True)
                gridLayout.addWidget(self.gamma, 8, 2)
                gridLayout.addWidget(QtWidgets.QLabel("Ro"), 9, 1)
                self.R0 = Entrada_con_unidades(
                    float, value=eq["R0"], readOnly=True)
                gridLayout.addWidget(self.R0, 9, 2)
                gridLayout.addWidget(QtWidgets.QLabel("ξo"), 10, 1)
                self.Xio = Entrada_con_unidades(
                    float, value=eq["Xio"], readOnly=True)
                gridLayout.addWidget(self.Xio, 10, 2)
                gridLayout.addWidget(QtWidgets.QLabel("Γo"), 11, 1)
                self.gam0 = Entrada_con_unidades(
                    float, value=eq["gam0"], readOnly=True)
                gridLayout.addWidget(self.gam0, 11, 2)
                gridLayout.addWidget(QtWidgets.QLabel("qd"), 12, 1)
                self.qd = Entrada_con_unidades(
                    float, value=eq["qd"], readOnly=True)
                gridLayout.addWidget(self.qd, 12, 2)
            elif eq["critical"] == 4:
                gridLayout.addWidget(QtWidgets.QLabel("γ"), 7, 1)
                self.gamma = Entrada_con_unidades(
                    float, value=eq["gamma"], readOnly=True)
                gridLayout.addWidget(self.gamma, 7, 2)
                gridLayout.addWidget(QtWidgets.QLabel("v"), 8, 1)
                self.v = Entrada_con_unidades(
                    float, value=eq["expo"], readOnly=True)
                gridLayout.addWidget(self.v, 8, 2)
                gridLayout.addWidget(QtWidgets.QLabel("α"), 9, 1)
                self.alfa = Entrada_con_unidades(
                    float, value=eq["alfa"], readOnly=True)
                gridLayout.addWidget(self.alfa, 9, 2)
                gridLayout.addWidget(QtWidgets.QLabel("β"), 10, 1)
                self.beta = Entrada_con_unidades(
                    float, value=eq["beta"], readOnly=True)
                gridLayout.addWidget(self.beta, 10, 2)
                gridLayout.addWidget(QtWidgets.QLabel("Γo"), 11, 1)
                self.Xio = Entrada_con_unidades(
                    float, value=eq["Xio"], readOnly=True)
                gridLayout.addWidget(self.Xio, 11, 2)
            gridLayout.addItem(QtWidgets.QSpacerItem(
                10, 10, QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding), 15, 3)


class Ui_Properties(QtWidgets.QDialog):
    """Dialog for select and sort shown properties in tables"""
    _default = [1, 0, 1, 0, 0, 1, 0, 1, 1]+[0]*(N_PROP-9)

    def __init__(self, config=None, parent=None):
        super(Ui_Properties, self).__init__(parent)
        if config and config.has_option("MEoS", "properties"):
            values = config.get("MEoS", "properties")
            if isinstance(values, str):
                values = eval(values)
            fase = config.getboolean("MEoS", "phase")
            self.order = config.get("MEoS", "propertiesOrder")
            if isinstance(self.order, str):
                self.order = eval(self.order)
        else:
            values = self._default
            fase = False
            self.order = list(range(N_PROP))

        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Select Properties"))
        layout = QtWidgets.QGridLayout(self)
        self.prop = QtWidgets.QTableWidget(len(ThermoAdvanced.properties()), 2)
        self.prop.verticalHeader().hide()
        self.prop.horizontalHeader().hide()
        self.prop.horizontalHeader().setStretchLastSection(True)
        self.prop.setGridStyle(QtCore.Qt.NoPen)
        self.prop.setColumnWidth(0, 18)
        self.prop.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.prop.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.prop.setItemDelegateForColumn(0, CheckEditor(self))
        for i, value in enumerate(values):
            if value == 1:
                val = "1"
            else:
                val = ""
            self.prop.setItem(i, 0, QtWidgets.QTableWidgetItem(val))
            name = ThermoAdvanced.propertiesName()[self.order[i]]
            self.prop.setItem(i, 1, QtWidgets.QTableWidgetItem(name))
            self.prop.setRowHeight(i, 20)
            self.prop.openPersistentEditor(self.prop.item(i, 0))
        self.prop.currentCellChanged.connect(self.comprobarBotones)
        self.prop.cellDoubleClicked.connect(self.toggleCheck)
        layout.addWidget(self.prop, 1, 1, 6, 1)

        self.ButtonArriba = QtWidgets.QToolButton()
        self.ButtonArriba.setIcon(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] +
            os.path.join("images", "button", "arrow-up.png"))))
        self.ButtonArriba.clicked.connect(self.Up)
        layout.addWidget(self.ButtonArriba, 3, 2, 1, 1)
        self.ButtonAbajo = QtWidgets.QToolButton()
        self.ButtonAbajo.setIcon(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] +
            os.path.join("images", "button", "arrow-down.png"))))
        self.ButtonAbajo.clicked.connect(self.Down)
        layout.addWidget(self.ButtonAbajo, 4, 2, 1, 1)

        self.checkFase = QtWidgets.QCheckBox(QtWidgets.QApplication.translate(
            "pychemqt", "Show bulk, liquid and vapor properties"))
        self.checkFase.setChecked(fase)
        layout.addWidget(self.checkFase, 7, 1, 1, 2)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Reset | QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.addButton(
            QtWidgets.QApplication.translate("pychemqt", "Mark all"),
            QtWidgets.QDialogButtonBox.ResetRole)
        self.buttonBox.addButton(
            QtWidgets.QApplication.translate("pychemqt", "No Mark"),
            QtWidgets.QDialogButtonBox.ResetRole)
        self.btYes = QtWidgets.QPushButton
        self.buttonBox.clicked.connect(self.buttonClicked)
        layout.addWidget(self.buttonBox, 8, 1, 1, 2)

    def toggleCheck(self, fila, columna):
        """Toggle check status with a doubleclick in row"""
        txt = self.prop.item(fila, 0).text()
        if txt == "0":
            newtxt = "1"
        else:
            newtxt = ""
        self.prop.item(fila, 0).setText(newtxt)

    def Down(self):
        """Change current selected row with next row"""
        i = self.prop.currentRow()
        txt = self.prop.item(i, 0).text()
        self.prop.item(i, 0).setText(self.prop.item(i+1, 0).text())
        self.prop.item(i+1, 0).setText(txt)
        item = self.prop.takeItem(i, 1)
        self.prop.setItem(i, 1, self.prop.takeItem(i+1, 1))
        self.prop.setItem(i+1, 1, item)
        self.prop.setCurrentCell(i+1, 0)
        self.order[i], self.order[i+1] = self.order[i+1], self.order[i]

    def Up(self):
        """Change current selected row with previous row"""
        i = self.prop.currentRow()
        txt = self.prop.item(i, 0).text()
        self.prop.item(i, 0).setText(self.prop.item(i-1, 0).text())
        self.prop.item(i-1, 0).setText(txt)
        item = self.prop.takeItem(i, 1)
        self.prop.setItem(i, 1, self.prop.takeItem(i-1, 1))
        self.prop.setItem(i-1, 1, item)
        self.prop.setCurrentCell(i-1, 0)
        self.order[i], self.order[i-1] = self.order[i-1], self.order[i]

    def buttonClicked(self, boton):
        """Actions for dialogbuttonbox functionality"""
        if self.buttonBox.buttonRole(boton) == \
                QtWidgets.QDialogButtonBox.AcceptRole:
            self.accept()
        elif self.buttonBox.buttonRole(boton) == \
                QtWidgets.QDialogButtonBox.RejectRole:
            self.reject()
        else:
            if boton == \
                    self.buttonBox.button(QtWidgets.QDialogButtonBox.Reset):
                values = self._default
            elif boton.text() == \
                    QtWidgets.QApplication.translate("pychemqt", "No Mark"):
                values = [0]*N_PROP
            else:
                values = [1]*N_PROP

            for i, propiedad in enumerate(values):
                if propiedad == 1:
                    val = "1"
                else:
                    val = ""
                self.prop.item(i, 0).setText(val)

    def properties(self):
        """Properties list"""
        value = []
        for i in range(self.prop.rowCount()):
            value.append(self.prop.cellWidget(i, 0).isChecked())
        return value

    def comprobarBotones(self, fila):
        """Check if button are enabled or disabled"""
        self.ButtonArriba.setEnabled(fila >= 1)
        self.ButtonAbajo.setEnabled(fila < self.prop.rowCount()-1)


# Table data
def createTabla(config, title, fluidos=None, parent=None):
    """Create TablaMEoS to add to mainwindow
        config: configparser instance with project configuration
        title: title for the table
        fluidos: optional array with meos instances to fill de table
        parent: mainwindow pointer
        """
    propiedades, keys, units = get_propiedades(config)

    # Add the unit suffix to properties title
    for i, unit in enumerate(units):
        sufx = unit.text()
        if not sufx:
            sufx = "[-]"
        propiedades[i] = propiedades[i]+os.linesep+sufx

    # Add two phases properties if requested
    if config.getboolean("MEoS", "phase"):
        for i in range(len(propiedades)-1, -1, -1):
            if keys[i] in ThermoAdvanced.propertiesPhase():
                txt = [propiedades[i]]
                prefix = QtWidgets.QApplication.translate("pychemqt", "Liquid")
                txt.append(prefix+os.linesep+propiedades[i])
                prefix = QtWidgets.QApplication.translate("pychemqt", "Vapour")
                txt.append(prefix+os.linesep+propiedades[i])
                propiedades[i:i+1] = txt
                units[i:i+1] = [units[i]]*3

    # Define common argument for TableMEoS
    kw = {}
    kw["horizontalHeader"] = propiedades
    kw["stretch"] = False
    kw["units"] = units
    kw["parent"] = parent

    if fluidos:
        # Generate a readOnly table filled of data
        tabla = TablaMEoS(len(propiedades), readOnly=True, **kw)
        data = []
        for fluido in fluidos:
            fila = _getData(fluido, keys, config.getboolean("MEoS", "phase"))
            data.append(fila)
        tabla.setData(data)

    else:
        # Generate a dinamic table empty
        columnInput = []
        for key in keys:
            if key in ["P", "T", "x", "rho", "v", "h", "s"]:
                columnInput.append(False)
            else:
                columnInput.append(True)
            if config.getboolean("MEoS", "phase") and \
                    key in ThermoAdvanced.propertiesPhase():
                columnInput.append(True)
                columnInput.append(True)
        kw["columnReadOnly"] = columnInput

        # Discard the keys from single phase state as input values
        if config.getboolean("MEoS", "phase"):
            for i in range(len(keys)-1, -1, -1):
                if keys[i] in ThermoAdvanced.propertiesPhase():
                    keys[i:i+1] = [keys[i], "", ""]
        kw["keys"] = keys

        tabla = TablaMEoS(len(propiedades), filas=1, **kw)

    prefix = QtWidgets.QApplication.translate("pychemqt", "Table")
    tabla.setWindowTitle(prefix+": "+title)
    tabla.resizeColumnsToContents()
    return tabla


def get_propiedades(config):
    """Procedure to get the properties to show in tables
    Input:
        config: configparser instance with mainwindow preferences
    Output:
        array with properties, key and units
    """
    booleanos = config.get("MEoS", "properties")
    order = config.get("MEoS", "propertiesOrder")
    if isinstance(booleanos, str):
        booleanos = eval(booleanos)
    if isinstance(order, str):
        order = eval(order)

    propiedades = []
    keys = []
    units = []
    for indice, bool in zip(order, booleanos):
        if bool:
            name, key, unit = ThermoAdvanced.properties()[indice]
            propiedades.append(name)
            keys.append(key)
            units.append(unit)
    return propiedades, keys, units


def _getData(fluid, keys, phase=True, unit=None, table=True):
    """Procedure to get values of properties in fluid
    Input:
        fluid: fluid instance to get values
        keys: array with desired parameter to get
        phase: boolean to get the properties values for both phases
        unit: unidades subclass
        table: boolean if the values are for a table, the none values are repr
            as text msg
    """
    print(keys)
    print(phase)
    print(unit)
    print(table)
    fila = []
    for i, key in enumerate(keys):
        if not key:
            continue
        p = fluid.__getattribute__(key)
        if isinstance(p, str):
            txt = p
        else:
            if unit and unit[i]:
                txt = p.__getattribute__(unit[i])
            else:
                txt = p.config()
        fila.append(txt)

        # Add two phases properties is requested
        if phase and key in ThermoAdvanced.propertiesPhase():
            # Liquid
            p = fluid.Liquido.__getattribute__(key)
            if isinstance(p, str):
                txt = p
            elif isinstance(p, unidades.unidad):
                if unit and unit[i]:
                    txt = p.__getattribute__(unit[i])
                else:
                    txt = p.config()
            else:
                txt = p
            fila.append(txt)
            # Gas
            p = fluid.Gas.__getattribute__(key)
            if isinstance(p, str):
                txt = p
            elif isinstance(p, unidades.unidad):
                if unit and unit[i]:
                    txt = p.__getattribute__(unit[i])
                else:
                    txt = p.config()
            else:
                txt = p
            fila.append(txt)
    return fila


class TablaMEoS(Tabla):
    """Tabla customize to show meos data, add context menu options, save and
    load support in project"""
    Plot = None
    icon = os.path.join(config.IMAGE_PATH, "button", "table.png")

    def __init__(self, *args, **kwargs):
        """Constructor with additional kwargs don't recognize in Tabla
        keys: array with keys properties
        units: array of unidades subclasses
        orderUnit: array of index of unit magnitud to show
        format: array of dict with numeric format
        """
        # Manage special parameter dont recognize in Tabla
        self.parent = kwargs.get("parent", None)
        if "keys" in kwargs:
            self.keys = kwargs["keys"]
            del kwargs["keys"]
        self.units = kwargs["units"]
        del kwargs["units"]
        if "orderUnit" in kwargs:
            self.orderUnit = kwargs["orderUnit"]
            del kwargs["orderUnit"]
        else:
            self.orderUnit = []
            for unit in self.units:
                if unit == unidades.Dimensionless:
                    self.orderUnit.append(0)
                else:
                    conf = self.parent.currentConfig
                    self.orderUnit.append(conf.getint('Units', unit.__name__))

        if "format" in kwargs:
            self.format = kwargs["format"]
            del kwargs["format"]
        else:
            self.format = [
                {"format": 1, "decimales": 6, "signo": False}]*args[0]

        super(TablaMEoS, self).__init__(*args, **kwargs)
        self.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(self.icon)))
        self.horizontalHeader().setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(
            self.hHeaderClicked)
        self.verticalHeader().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.verticalHeader().customContextMenuRequested.connect(
            self.vHeaderClicked)
        self.itemSelectionChanged.connect(self.selectPoint)
        self.data = []
        if not self.readOnly:
            self.cellChanged.connect(self.calculatePoint)

    def _getPlot(self):
        """Return plot if it's loaded"""
        if not self.Plot:
            windows = self.parent.centralwidget.currentWidget().subWindowList()
            for window in windows:
                widget = window.widget()
                if isinstance(widget, PlotMEoS):
                    self.Plot = widget
                    break
        return self.Plot

    def hHeaderClicked(self, event):
        """Show dialog to config format and unit"""
        col = self.horizontalHeader().logicalIndexAt(event)
        unit = self.units[col]
        dialog = NumericFactor(self.format[col], unit, self.orderUnit[col])
        if dialog.exec_():
            # Check unit change
            if unit != unidades.Dimensionless and \
                    dialog.unit.currentIndex() != self.orderUnit[col]:
                for i, fila in enumerate(self.data):
                    conf = unit.__units__[self.orderUnit[col]]
                    key = unit.__units__[dialog.unit.currentIndex()]
                    value = unit(fila[col], conf).__getattribute__(key)
                    self.data[i][col] = value
                self.orderUnit[col] = dialog.unit.currentIndex()
                txt = self.horizontalHeaderItem(
                    col).text().split(os.linesep)[0]
                txt += os.linesep+unit.__text__[dialog.unit.currentIndex()]
                self.setHorizontalHeaderItem(
                    col, QtWidgets.QTableWidgetItem(txt))

            # Check format change
            self.format[col] = dialog.args()
            self.setStr()
            self.resizeColumnToContents(col)
        range = QtWidgets.QTableWidgetSelectionRange(
            0, col, self.rowCount()-1, col)
        self.setRangeSelected(range, True)

    def vHeaderClicked(self, position):
        """Show dialog to manage item in table"""
        row = self.verticalHeader().logicalIndexAt(position)
        rows = []
        for item in self.selectedItems():
            if item.row() not in rows:
                rows.append(item.row())
        rows.sort(reverse=True)

        actionCopy = createAction(
            QtWidgets.QApplication.translate("pychemqt", "&Copy"),
            slot=self.copy, shortcut=QtGui.QKeySequence.Copy,
            icon=os.environ["pychemqt"] +
            os.path.join("images", "button", "editCopy"),
            parent=self)
        if not self.selectedItems():
            actionCopy.setEnabled(False)

        actionDelete = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Delete Point"),
            icon=os.environ["pychemqt"]+"/images/button/editDelete",
            slot=partial(self.delete, rows), parent=self)
        if not rows:
            actionDelete.setEnabled(False)

        actionInsert = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Insert Point"),
            icon=os.environ["pychemqt"]+"/images/button/add",
            slot=partial(self.add, row), parent=self)

        menu = QtWidgets.QMenu()
        menu.addAction(actionCopy)
        menu.addSeparator()
        menu.addAction(actionDelete)
        menu.addAction(actionInsert)
        menu.exec_(self.mapToGlobal(position))

    def delete(self, rows):
        """Delete rows from table and for saved data"""
        self.parent.statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Deleting point..."))
        QtWidgets.QApplication.processEvents()

        # Delete point from table
        for row in rows:
            self.removeRow(row)
            delete(self.data, row)

        # Update verticalHeader
        for row in range(self.rowCount()):
            self.setVHeader(row)

        # Delete point from data plot
        plot = self._getPlot()
        if plot:
            data = plot._getData()
            pref = QtWidgets.QApplication.translate("pychemqt", "Table from")
            title = self.windowTitle().split(pref)[1][1:]
            for row in rows:
                if title == QtWidgets.QApplication.translate(
                        "pychemqt", "Melting Line"):
                    for x in ThermoAdvanced.propertiesKey():
                        del data["melting"][x][row]
                elif title == QtWidgets.QApplication.translate(
                        "pychemqt", "Sublimation Line"):
                    for x in ThermoAdvanced.propertiesKey():
                        del data["sublimation"][x][row]
                elif title == QtWidgets.QApplication.translate(
                        "pychemqt", "Saturation Line") or \
                        title == QtWidgets.QApplication.translate(
                            "pychemqt", "Liquid Saturation Line"):
                    for x in ThermoAdvanced.propertiesKey():
                        del data["saturation_0"][x][row]
                elif title == QtWidgets.QApplication.translate(
                        "pychemqt", "Vapor Saturation Line"):
                    for x in ThermoAdvanced.propertiesKey():
                        del data["saturation_1"][x][row]
                else:
                    units = {"P": unidades.Pressure,
                             "T": unidades.Temperature,
                             "h": unidades.Enthalpy,
                             "s": unidades.Enthalpy,
                             "v": unidades.SpecificVolume,
                             "rho": unidades.Density}
                    var = str(title.split(" = ")[0])
                    txt = title.split(" = ")[1]
                    unit = units[var]
                    value = float(txt.split(" ")[0])
                    stdValue = unit(value, "conf")
                    for x in ThermoAdvanced.propertiesKey():
                        del data[var][stdValue][x][row]
            plot._saveData(data)

            # Delete point from data
            for line in plot.plot.ax.lines:
                if str(line.get_label()) == str(title):
                    xdata = line._x
                    ydata = line._y
                    for row in rows:
                        xdata = delete(xdata, row)
                        ydata = delete(ydata, row)
                    line.set_xdata(xdata)
                    line.set_ydata(ydata)
                    plot.plot.draw()
                    break
        self.parent.statusbar.clearMessage()

    def add(self, row):
        """Add point to a table and to saved file"""
        pref = QtWidgets.QApplication.translate("pychemqt", "Table from ")
        if pref in self.windowTitle():
            title = self.windowTitle().split(pref)[1]
            melting = title == QtWidgets.QApplication.translate(
                "pychemqt", "Melting Line")
        else:
            melting = False

        dlg = AddPoint(self.Point._new(), melting, self.parent)
        if dlg.exec_():
            self.blockSignals(True)
            if dlg.checkBelow.isChecked():
                row += 1

            plot = self.Plot
            if plot is None:
                plot = self._getPlot()

            if plot is None:
                # If table has no associated plot, define as normal point
                units = []
                for ui, order in zip(self.units, self.orderUnit):
                    if ui is unidades.Dimensionless:
                        units.append("")
                    else:
                        units.append(ui.__units__[order])
                phase = self.parent.currentConfig.getboolean("MEoS", "phase")
                datatoTable = _getData(dlg.fluid, self.keys, phase, units)
            else:
                # If table has a associated plot, use the values of that
                datatoTable = []
                datatoTable.append(dlg.fluid.__getattribute__(plot.x).config())
                datatoTable.append(dlg.fluid.__getattribute__(plot.y).config())

            # Add point to table
            self.addRow(index=row)
            self.setRow(row, datatoTable)

            # Update verticalHeader
            for row in range(self.rowCount()):
                self.setVHeader(row)

            # Add point to data plot
            if plot is None:
                return

            data = plot._getData()
            if title == QtWidgets.QApplication.translate(
                    "pychemqt", "Melting Line"):
                for x in ThermoAdvanced.propertiesKey():
                    data["melting"][x].insert(
                        row, dlg.fluid.__getattribute__(x))
            elif title == QtWidgets.QApplication.translate(
                    "pychemqt", "Sublimation Line"):
                for x in ThermoAdvanced.propertiesKey():
                    data["sublimation"].insert(
                        row, dlg.fluid.__getattribute__(x))
            elif title == QtWidgets.QApplication.translate(
                    "pychemqt", "Saturation Line") or \
                    title == QtWidgets.QApplication.translate(
                        "pychemqt", "Liquid Saturation Line"):
                for x in ThermoAdvanced.propertiesKey():
                    data["saturation_0"].insert(
                        row, dlg.fluid.__getattribute__(x))
            elif title == QtWidgets.QApplication.translate(
                    "pychemqt", "Vapor Saturation Line"):
                for x in ThermoAdvanced.propertiesKey():
                    data["saturation_1"].insert(
                        row, dlg.fluid.__getattribute__(x))
            else:
                units = {"P": unidades.Pressure,
                         "T": unidades.Temperature,
                         "h": unidades.Enthalpy,
                         "s": unidades.Enthalpy,
                         "v": unidades.SpecificVolume,
                         "rho": unidades.Density}
                var = str(title.split(" = ")[0])
                txt = title.split(" = ")[1]
                unit = units[var]
                value = float(txt.split(" ")[0])
                stdValue = unit(value, "conf")

                for x in ThermoAdvanced.propertiesKey():
                    data[var][stdValue][x].insert(
                        row, dlg.fluid.__getattribute__(x))
            plot._saveData(data)

            # Add point to data
            for line in plot.plot.ax.lines:
                if str(line.get_label()) == str(title):
                    xdata = insert(line._x, row, datatoTable[0])
                    ydata = insert(line._y, row, datatoTable[1])
                    line.set_xdata(xdata)
                    line.set_ydata(ydata)
                    plot.plot.draw()
                    break

            self.blockSignals(False)

    def selectPoint(self):
        """Show selected point in table in asociated plot if exist"""
        plot = self._getPlot()
        if plot:
            # Remove old selected point if exist
            for i, line in enumerate(plot.plot.ax.lines):
                if line.get_label() == QtWidgets.QApplication.translate(
                        "pychemqt", "Selected Point"):
                    del line
                    del plot.plot.ax.lines[i]

            # Add new selected points
            x = []
            y = []
            for item in self.selectedItems():
                if item.column():
                    y.append(float(item.text()))
                else:
                    x.append(float(item.text()))
            label = QtWidgets.QApplication.translate(
                "pychemqt", "Selected Point")
            plot.plot.ax.plot(x, y, 'ro', label=label)
            plot.plot.draw()

    def calculatePoint(self, row, column):
        """Add new value to kwargs for point, and show properties if it is
        calculable
        row, column: index for modified cell in table"""
        txt = self.item(row, column).text()
        if not txt:
            return

        key = self.keys[column]
        unit = self.units[column]
        if unit is unidades.Dimensionless:
            value = float(self.item(row, column).text())
        else:
            data = float(self.item(row, column).text())
            value = unit(data, unit.__units__[self.orderUnit[column]])
        print(key, value)
        print(self.Point)
        self.Point(**{key: value})

        # If the Point is calculated, get data
        if self.Point.status:
            units = []
            for ui, order in zip(self.units, self.orderUnit):
                if ui is unidades.Dimensionless:
                    units.append("")
                else:
                    units.append(ui.__units__[order])
            phase = self.parent.currentConfig.getboolean("MEoS", "phase")
            data = _getData(self.Point, self.keys, phase, units)
            self.setRow(row, data)
            self.Point = self.Point._new()

            self.addRow()
            self.setCurrentCell(row+1, column)

    def setData(self, data):
        """Override Tabla method to adapt functionality"""
        if self.readOnly:
            self.data = data
            self.setStr()
        else:
            for i, row in enumerate(data):
                self.setRow(i, row)
        self.resizeColumnsToContents()

    def setStr(self):
        """Add data as string to cell table"""
        for fila, array in enumerate(self.data):
            if fila >= self.rowCount():
                self.addRow()
            for columna, data in enumerate(array):
                if isinstance(data, str):
                    txt = data
                else:
                    txt = representacion(data, **self.format[columna])
                self.setValue(fila, columna, txt)

    def setRow(self, row, data):
        """Add data to a row"""
        self.blockSignals(True)
        self.data.insert(row, data)
        for column, data in enumerate(data):
            if isinstance(data, str):
                txt = data
            else:
                txt = representacion(data, **self.format[column])
            self.setValue(row, column, txt)
        self.resizeColumnsToContents()

        # Set calculate point readOnly
        if not self.readOnly:
            flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            color = config.Preferences.get("General", 'Color_ReadOnly')
            for i, bool in enumerate(self.columnReadOnly):
                if not bool:
                    self.item(row, i).setFlags(flags)
                    self.item(row, i).setBackground(QtGui.QColor(color))
        self.blockSignals(False)

    def contextMenuEvent(self, event):
        """Show context menu over cell"""
        menu = QtWidgets.QMenu()
        actionCopy = createAction(
            QtWidgets.QApplication.translate("pychemqt", "&Copy"),
            slot=partial(self.copy, event), shortcut=QtGui.QKeySequence.Copy,
            icon=os.environ["pychemqt"] +
            os.path.join("images", "button", "editCopy"),
            parent=self)
        export = createAction(
            QtWidgets.QApplication.translate("pychemqt", "E&xport to csv"),
            self.exportCSV,
            icon=os.environ["pychemqt"] +
            os.path.join("images", "button", "export"),
            tip=QtWidgets.QApplication.translate(
                "pychemqt", "Export table to file"),
            parent=self)
        menu.addAction(actionCopy)
        menu.addSeparator()
        menu.addAction(export)
        menu.exec_(event.globalPos())

    def copy(self, event=None):
        """Copy selected values to clipboard"""
        txt = [w.text() for w in self.selectedItems()]
        QtWidgets.QApplication.clipboard().setText(" ".join(txt))

    def exportCSV(self):
        """Export data table as a csv file"""
        if self.parent.currentFilename:
            dir = os.path.dirname(str(self.parent.currentFilename))
        else:
            dir = "."

        pat = []
        pat.append(QtWidgets.QApplication.translate(
            "pychemqt", "CSV files") + " (*.csv)")
        if os.environ["ezodf"] == "True":
            pat.append(QtWidgets.QApplication.translate(
                "pychemqt", "Libreoffice spreadsheet files") + " (*.ods)")
        if os.environ["xlwt"] == "True":
            pat.append(QtWidgets.QApplication.translate(
                "pychemqt",
                "Microsoft Excel 97/2000/XP/2003 XML") + " (*.xls)")
        if os.environ["openpyxl"] == "True":
            pat.append(QtWidgets.QApplication.translate(
                "pychemqt", "Microsoft Excel 2007/2010 XML") + " (*.xlsx)")
        patron = ";;".join(pat)

        fname, ext = QtWidgets.QFileDialog.getSaveFileName(
            self, QtWidgets.QApplication.translate(
                "pychemqt", "Export table to file"), dir, patron)
        if fname and ext:
            ext = ext.split(".")[-1][:-1]
            exportTable(self.data, fname, ext, self.horizontalHeaderLabel)

    def writeToJSON(self, data):
        """Write instance parameter to file"""
        data["column"] = self.columnCount()

        # Save titles
        data["title"] = self.windowTitle()
        data["htitle"] = []
        for column in range(data["column"]):
            data["htitle"].append(self.horizontalHeaderItem(column).text())

        # Save units as index
        all = unidades._all
        all.append(unidades.Dimensionless)
        data["unit"] = [all.index(unit) for unit in self.units]

        # Save keys if necessary
        data["readOnly"] = self.readOnly
        if not self.readOnly:
            if isinstance(self.Point, meos.MEoS):
                data["method"] = "meos"
                data["fluid"] = mEoS.__all__.index(self.Point.__class__)
                data["external_dependences"] = ""
            elif isinstance(self.Point, coolProp.CoolProp):
                data["method"] = "coolprop"
                data["fluid"] = self.Point.kwargs["ids"][0]
                data["external_dependences"] = "CoolProp"
            else:
                data["method"] = "refprop"
                data["fluid"] = self.Point.kwargs["ids"][0]
                data["external_dependences"] = "refprop"

            data["keys"] = self.keys
            data["columnReadOnly"] = self.columnReadOnly

        # Save order unit
        data["orderUnit"] = self.orderUnit

        # Save format
        data["format"] = self.format

        # Save data if exist
        data["data"] = self.data

    @classmethod
    def readFromJSON(cls, data, parent):
        """Load data table from saved file"""

        # Get units
        all = unidades._all
        for i, u in enumerate(all):
            print(i, u)
        all.append(unidades.Dimensionless)
        units = [all[i] for i in data["unit"]]

        # Create Tabla
        kwargs = {}
        kwargs["horizontalHeader"] = data["htitle"]
        kwargs["format"] = data["format"]
        kwargs["stretch"] = False
        kwargs["parent"] = parent
        kwargs["units"] = units
        kwargs["orderUnit"] = data["orderUnit"]

        if data["readOnly"]:
            kwargs["readOnly"] = True
        else:
            kwargs["filas"] = len(data["data"])+1
            kwargs["keys"] = data["keys"]
            kwargs["columnReadOnly"] = data["columnReadOnly"]

        tabla = TablaMEoS(data["column"], **kwargs)
        tabla.setWindowTitle(data["title"])
        tabla.setData(data["data"])
        if not data["readOnly"]:
            if data["method"] == "meos":
                fluid = mEoS.__all__[data["fluid"]]()
            elif data["method"] == "coolprop":
                fluid = coolProp.CoolProp(ids=[data["fluid"]])
            elif data["method"] == "refprop":
                fluid = refProp.RefProp(ids=[data["fluid"]])
            tabla.Point = fluid

        return tabla


class Ui_Saturation(QtWidgets.QDialog):
    """Dialog to define input for a two-phase saturation table calculation"""
    def __init__(self, config=None, parent=None):
        """config: instance with project config to set initial values"""
        super(Ui_Saturation, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Saturation Table"))
        layout = QtWidgets.QGridLayout(self)

        gboxType = QtWidgets.QGroupBox(
            QtWidgets.QApplication.translate("pychemqt", "Interphase"))
        layout.addWidget(gboxType, 1, 1, 1, 2)
        layoutg1 = QtWidgets.QGridLayout(gboxType)
        self.VL = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "Vapor-Liquid (boiling line)"))
        layoutg1.addWidget(self.VL, 1, 1)
        self.SL = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "Solid-Liquid (melting line"))
        layoutg1.addWidget(self.SL, 2, 1)
        self.SV = QtWidgets.QRadioButton(QtWidgets.QApplication.translate(
            "pychemqt", "Solid-Vapor (Sublimation line)"))
        layoutg1.addWidget(self.SV, 3, 1)

        groupboxVariar = QtWidgets.QGroupBox(
            QtWidgets.QApplication.translate("pychemqt", "Change"))
        layout.addWidget(groupboxVariar, 1, 3, 1, 2)
        layoutg2 = QtWidgets.QGridLayout(groupboxVariar)
        self.VariarTemperatura = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate("pychemqt", "Temperature"))
        self.VariarTemperatura.toggled.connect(self.updateVar)
        layoutg2.addWidget(self.VariarTemperatura, 1, 1)
        self.VariarPresion = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate("pychemqt", "Pressure"))
        self.VariarPresion.toggled.connect(self.updateVar)
        layoutg2.addWidget(self.VariarPresion, 2, 1)
        self.VariarXconT = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate(
                "pychemqt", "Quality at fixed temperature"))
        self.VariarXconT.toggled.connect(self.updateVar)
        layoutg2.addWidget(self.VariarXconT, 3, 1)
        self.VariarXconP = QtWidgets.QRadioButton(
            QtWidgets.QApplication.translate(
                "pychemqt", "Quality at fixed pressure"))
        self.VariarXconP.toggled.connect(self.updateVar)
        layoutg2.addWidget(self.VariarXconP, 4, 1)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line, 2, 1, 1, 4)

        self.labelFix = QtWidgets.QLabel()
        layout.addWidget(self.labelFix, 4, 3)
        self.variableFix = Entrada_con_unidades(float)
        layout.addWidget(self.variableFix, 4, 4)
        self.labelinicial = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Initial"))
        layout.addWidget(self.labelinicial, 4, 1)
        self.Inicial = Entrada_con_unidades(float)
        layout.addWidget(self.Inicial, 4, 2)
        self.labelfinal = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Final"))
        layout.addWidget(self.labelfinal, 5, 1)
        self.Final = Entrada_con_unidades(float)
        layout.addWidget(self.Final, 5, 2)
        self.labelincremento = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Increment"))
        layout.addWidget(self.labelincremento, 6, 1)
        self.Incremento = Entrada_con_unidades(float)
        layout.addWidget(self.Incremento, 6, 2)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 10, 1, 1, 4)

        if config:
            self.fluido = getClassFluid(config)
            if isinstance(self.fluido, meos.MEoS) and (
                self.fluido._Melting_Pressure != meos.MEoS._Melting_Pressure or
                    self.fluido._melting):
                self.SL.setEnabled(True)
            else:
                self.SL.setEnabled(False)
            if isinstance(self.fluido, meos.MEoS) and (
                self.fluido._sublimation or
                self.fluido._Sublimation_Pressure !=
                    meos.MEoS._Sublimation_Pressure):
                self.SV.setEnabled(True)
            else:
                self.SV.setEnabled(False)

        self.VL.setChecked(True)
        self.VariarTemperatura.setChecked(True)
        self.updateVary()
        self.VL.toggled.connect(self.updateVary)

    def updateVary(self):
        """Update state for option to choose for properties to change"""
        self.VariarXconP.setEnabled(self.VL.isChecked())
        self.VariarXconT.setEnabled(self.VL.isChecked())
        self.VariarTemperatura.setChecked(not self.VL.isChecked())

    def updateVar(self, bool):
        """Update input values units and text"""
        if bool:
            # Select initial values
            fix, inicial, final, step = 0, 0, 0, 0
            if self.VL.isChecked():
                if self.sender() == self.VariarXconT:
                    fix = ceil((self.fluido.Tc-self.fluido.Tt)/2)
                    inicial = 0
                    final = 1
                    step = 0.1
                elif self.sender() == self.VariarXconP:
                    fix = ceil(self.fluido.Pc/2)
                    inicial = 0
                    final = 1
                    step = 0.1
                elif self.sender() == self.VariarTemperatura:
                    inicial = ceil(self.fluido.Tt)
                    final = floor(self.fluido.Tc)
                    step = 1.

            self.Inicial.deleteLater()
            self.Final.deleteLater()
            self.Incremento.deleteLater()
            if self.sender() == self.VariarXconT:
                self.labelFix.setVisible(True)
                self.labelFix.setText(unidades.Temperature.__title__)
                self.variableFix.deleteLater()
                self.variableFix = Entrada_con_unidades(
                    unidades.Temperature, value=fix)
                self.layout().addWidget(self.variableFix, 4, 4)
                unidadVariable = float
                self.labelinicial.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Initial quality"))
                self.labelfinal.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Final quality"))

            elif self.sender() == self.VariarXconP:
                self.labelFix.setVisible(True)
                self.labelFix.setText(unidades.Pressure.__title__)
                self.variableFix.deleteLater()
                self.variableFix = Entrada_con_unidades(
                    unidades.Pressure, value=fix)
                self.layout().addWidget(self.variableFix, 4, 4)
                unidadVariable = float
                self.labelinicial.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Initial quality"))
                self.labelfinal.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Final quality"))

            elif self.sender() == self.VariarTemperatura:
                self.labelFix.setVisible(False)
                self.variableFix.setVisible(False)
                unidadVariable = unidades.Temperature
                self.labelinicial.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Initial temperature"))
                self.labelfinal.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Final temperature"))

            else:
                self.labelFix.setVisible(False)
                self.variableFix.setVisible(False)
                unidadVariable = unidades.Pressure
                self.labelinicial.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Initial pressure"))
                self.labelfinal.setText(QtWidgets.QApplication.translate(
                    "pychemqt", "Final pressure"))

            self.Inicial = Entrada_con_unidades(unidadVariable, value=inicial)
            self.Final = Entrada_con_unidades(unidadVariable, value=final)
            if unidadVariable == unidades.Temperature:
                unidadDelta = unidades.DeltaT
            elif unidadVariable == unidades.Pressure:
                unidadDelta = unidades.DeltaP
            else:
                unidadDelta = unidadVariable

            self.Incremento = Entrada_con_unidades(unidadDelta, value=step)
            self.layout().addWidget(self.Inicial, 4, 2)
            self.layout().addWidget(self.Final, 5, 2)
            self.layout().addWidget(self.Incremento, 6, 2)


class Ui_Isoproperty(QtWidgets.QDialog):
    """Dialog to define input for isoproperty table calculations"""
    propiedades = [
        QtWidgets.QApplication.translate("pychemqt", "Temperature"),
        QtWidgets.QApplication.translate("pychemqt", "Pressure"),
        QtWidgets.QApplication.translate("pychemqt", "Density"),
        QtWidgets.QApplication.translate("pychemqt", "Volume"),
        QtWidgets.QApplication.translate("pychemqt", "Enthalpy"),
        QtWidgets.QApplication.translate("pychemqt", "Entropy"),
        QtWidgets.QApplication.translate("pychemqt", "Internal Energy")]
    unidades = [unidades.Temperature, unidades.Pressure, unidades.Density,
                unidades.SpecificVolume, unidades.Enthalpy,
                unidades.SpecificHeat, unidades.Enthalpy, float]
    keys = ["T", "P", "rho", "v", "h", "s", "u", "x"]

    def __init__(self, parent=None):
        super(Ui_Isoproperty, self).__init__(parent)
        self.setWindowTitle(QtWidgets.QApplication.translate(
            "pychemqt", "Specify Isoproperty Table"))
        layout = QtWidgets.QGridLayout(self)

        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Hold constant")), 1, 1)
        self.fix = QtWidgets.QComboBox()
        for propiedad in self.propiedades:
            self.fix.addItem(propiedad)
        self.fix.currentIndexChanged.connect(self.actualizarUI)
        layout.addWidget(self.fix, 1, 2)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Vary")), 2, 1)
        self.vary = QtWidgets.QComboBox()
        self.vary.currentIndexChanged.connect(self.actualizarVariable)
        layout.addWidget(self.vary, 2, 2)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line, 3, 1, 1, 2)

        self.labelFix = QtWidgets.QLabel()
        layout.addWidget(self.labelFix, 4, 1)
        self.variableFix = Entrada_con_unidades(float)
        layout.addWidget(self.variableFix, 4, 2)
        self.labelinicial = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Initial"))
        layout.addWidget(self.labelinicial, 5, 1)
        self.Inicial = Entrada_con_unidades(float)
        layout.addWidget(self.Inicial, 5, 2)
        self.labelfinal = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Final"))
        layout.addWidget(self.labelfinal, 6, 1)
        self.Final = Entrada_con_unidades(float)
        layout.addWidget(self.Final, 6, 2)
        self.labelincremento = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Increment"))
        layout.addWidget(self.labelincremento, 7, 1)
        self.Incremento = Entrada_con_unidades(float)
        layout.addWidget(self.Incremento, 7, 2)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 10, 1, 1, 2)

        self.actualizarUI(0)

    def actualizarUI(self, indice):
        self.vary.clear()
        propiedades = self.propiedades[:]
        if indice <= 1:
            propiedades.append(QtWidgets.QApplication.translate(
                "pychemqt", "Quality"))
        del propiedades[indice]
        for propiedad in propiedades:
            self.vary.addItem(propiedad)
        self.labelFix.setText(self.propiedades[indice])
        self.variableFix.deleteLater()
        self.variableFix = Entrada_con_unidades(self.unidades[indice])
        self.layout().addWidget(self.variableFix, 4, 2)

    def actualizarVariable(self, indice):
        self.Inicial.deleteLater()
        self.Final.deleteLater()
        self.Incremento.deleteLater()
        if indice >= self.fix.currentIndex():
            indice += 1
        self.Inicial = Entrada_con_unidades(self.unidades[indice])
        self.Final = Entrada_con_unidades(self.unidades[indice])
        self.Incremento = Entrada_con_unidades(self.unidades[indice])
        self.layout().addWidget(self.Inicial, 5, 2)
        self.layout().addWidget(self.Final, 6, 2)
        self.layout().addWidget(self.Incremento, 7, 2)


class AddPoint(QtWidgets.QDialog):
    """Dialog to add new point to line2D"""
    keys = ["T", "P", "x", "rho", "v", "h", "s", "u"]

    def __init__(self, fluid, melting=False, parent=None):
        """
        fluid: initial fluid instance
        melting: boolean to add melting line calculation
        """
        super(AddPoint, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Add Point to line"))
        layout = QtWidgets.QGridLayout(self)
        self.fluid = fluid

        self.Inputs = []
        for i, (title, key, unit) in enumerate(meos.inputData):
            layout.addWidget(QtWidgets.QLabel(title), i, 1)
            if unit is unidades.Dimensionless:
                entrada = Entrada_con_unidades(float)
            else:
                entrada = Entrada_con_unidades(unit)
            entrada.valueChanged.connect(partial(self.update, key))
            self.Inputs.append(entrada)
            layout.addWidget(entrada, i, 2)

        self.status = Status(self.fluid.status, self.fluid.msg)
        layout.addWidget(self.status, i+1, 1, 1, 2)

        if isinstance(fluid, meos.MEoS) and fluid._melting:
            self.checkMelting = QtWidgets.QRadioButton(
                QtWidgets.QApplication.translate("pychemqt", "Melting Point"))
            self.checkMelting.setChecked(melting)
            layout.addWidget(self.checkMelting, i+2, 1, 1, 2)
            i += 1
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "To")), i+2, 1)
        self.To = Entrada_con_unidades(unidades.Temperature)
        self.To.valueChanged.connect(partial(self.update, "To"))
        layout.addWidget(self.To, i+2, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "rhoo")), i+3, 1)
        self.rhoo = Entrada_con_unidades(unidades.Density)
        self.rhoo.valueChanged.connect(partial(self.update, "rhoo"))
        layout.addWidget(self.rhoo, i+3, 2)

        self.checkBelow = QtWidgets.QCheckBox(QtWidgets.QApplication.translate(
            "pychemqt", "Add below selected point"))
        layout.addWidget(self.checkBelow, i+4, 1, 1, 2)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Reset | QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.clicked.connect(self.click)
        layout.addWidget(self.buttonBox, i+5, 1, 1, 2)

    def click(self, button):
        """Manage mouse click event over buttonbox"""
        if QtWidgets.QDialogButtonBox.Reset == \
                self.buttonBox.standardButton(button):
            self.reset()
        elif QtWidgets.QDialogButtonBox.Ok == \
                self.buttonBox.standardButton(button):
            self.accept()
        elif QtWidgets.QDialogButtonBox.Cancel == \
                self.buttonBox.standardButton(button):
            self.reject()

    def update(self, key, value):
        """Update fluid instance with new parameter key with value"""
        self.status.setState(4)
        QtWidgets.QApplication.processEvents()
        if isinstance(self.fluid, meos.MEoS) and self.fluid._melting and \
                self.checkMelting.isChecked() and key == "T":
            P = self.fluid._Melting_Pressure(value)
            self.fluid(**{key: value, "P": P})
        else:
            self.fluid(**{key: value})
        if self.fluid.status in (1, 3):
            self.fill(self.fluid)
        self.status.setState(self.fluid.status, self.fluid.msg)

    def fill(self, fluid):
        """Fill dialog widget with fluid properties values"""
        self.blockSignals(True)
        Config = ConfigParser()
        Config.read(config.conf_dir + "pychemqtrc")
        for key, input in zip(self.keys, self.Inputs):
            input.setValue(fluid.__getattribute__(key))
            if fluid.kwargs[key]:
                input.setResaltado(True)
            else:
                input.setResaltado(False)
        self.blockSignals(False)

    def reset(self):
        """Reset dialog widgets to initial clear status"""
        self.fluid = self.fluid.__class__()
        self.status.setState(self.fluid.status, self.fluid.msg)
        self.rhoo.clear()
        self.To.clear()
        for input in self.Inputs:
            input.clear()
            input.setResaltado(False)


# Plot data
class PlotMEoS(QtWidgets.QWidget):
    """Plot widget to show meos plot data, add context menu options"""
    def __init__(self, dim, toolbar=False, filename="", parent=None):
        """constructor
        Input:
            dim: dimension of plot, | 2 | 3
            toolbar: boolean to add the matplotlib toolbar
            filename: filename for data
        """
        super(PlotMEoS, self).__init__(parent)
        self.parent = parent
        self.dim = dim
        self.filename = filename
        self.notes = []

        layout = QtWidgets.QVBoxLayout(self)
        self.plot = plot.matplotlib(dim)

        self.plot.lx = self.plot.ax.axhline(c="#888888", ls=":")  # horiz line
        self.plot.ly = self.plot.ax.axvline(c="#888888", ls=":")  # vert line

        self.plot.lx.set_visible(False)
        self.plot.ly.set_visible(False)

        layout.addWidget(self.plot)
        self.toolbar = plot.NavigationToolbar2QT(self.plot, self.plot)
        self.toolbar.setVisible(toolbar)
        layout.addWidget(self.toolbar)

        self.editAxesAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Edit &Axis"),
            icon=os.environ["pychemqt"]+"/images/button/editor",
            slot=self.editAxis, parent=self)
        self.editAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Edit &Plot"),
            slot=self.edit,
            icon=os.environ["pychemqt"]+"/images/button/fit",
            parent=self)
        self.editMarginAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Edit &Margins"),
            slot=self.toolbar.configure_subplots, parent=self)
        self.saveAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "&Save Plot"),
            slot=self.toolbar.save_figure,
            icon=os.environ["pychemqt"]+"/images/button/fileSave", parent=self)
        self.toolbarVisibleAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Toggle &Toolbar"),
            self.toolbar.setVisible, checkable=True, parent=self)
        self.gridToggleAction = createAction(
            QtWidgets.QApplication.translate("pychemqt", "Toggle &Grid"),
            self.grid, checkable=True, parent=self)
        grid = config.Preferences.getboolean("MEOS", "grid")
        self.gridToggleAction.setChecked(grid)

        if dim == 2:
            self.plot.fig.canvas.mpl_connect('button_press_event', self.click)
        else:
            self.editMarginAction.setEnabled(False)

    def contextMenuEvent(self, event):
        """Create context menu"""
        menuTable = QtWidgets.QMenu(
            QtWidgets.QApplication.translate("pychemqt", "Tabulated data"))
        menuTable.setIcon(
            QtGui.QIcon(os.environ["pychemqt"]+"/images/button/table"))
        for linea in self.plot.ax.lines:
            action = createAction(linea.get_label(),
                                  slot=partial(self.table, linea), parent=self)
            menuTable.addAction(action)

        menu = QtWidgets.QMenu()
        menu.addAction(self.editAxesAction)
        menu.addAction(self.editAction)
        menu.addAction(self.editMarginAction)
        menu.addSeparator()
        menu.addAction(self.saveAction)
        menu.addAction(menuTable.menuAction())
        menu.addSeparator()
        menu.addAction(self.toolbarVisibleAction)
        menu.addAction(self.gridToggleAction)
        menu.exec_(event.globalPos())

        if self.plot.ax._gridOn:
            self.gridToggleAction.setChecked(True)

    def grid(self, bool):
        self.plot.ax.grid(bool)
        self.plot.ax._gridOn = bool
        self.plot.draw()

    def edit(self):
        dialog = EditPlot(self, self.parent)
        dialog.show()

    def editAxis(self):
        dialog = EditAxis(self.plot)
        dialog.exec_()

    def table(self, obj):
        """Export plot data to table
        Input:
            obj: object (Line2D instance) to show data
        """
        xtxt = meos.propiedades[meos.keys.index(self.x)]
        ytxt = meos.propiedades[meos.keys.index(self.y)]
        xunit = meos.units[meos.keys.index(self.x)]
        yunit = meos.units[meos.keys.index(self.y)]
        HHeader = [xtxt+os.linesep+xunit.text(), ytxt+os.linesep+yunit.text()]
        units = [xunit, yunit]
        if self.dim == 3:
            ztxt = meos.propiedades[meos.keys.index(self.z)]
            zunit = meos.units[meos.keys.index(self.z)]
            HHeader.append(ztxt+os.linesep+zunit.text())
            units.append(zunit)
            data = obj._verts3d
        else:
            data = obj.get_data(orig=True)

        tabla = TablaMEoS(self.dim, horizontalHeader=HHeader, units=units,
                          stretch=False, readOnly=True, parent=self.parent)
        tabla.setData(transpose(data))
        tabla.verticalHeader().setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu)

        title = QtWidgets.QApplication.translate("pychemqt", "Table from") + \
            " " + obj.get_label()
        tabla.setWindowTitle(title)
        self.parent.centralwidget.currentWidget().addSubWindow(tabla)
        tabla.show()

    def _getData(self):
        """Get data from file"""
        filenameHard = os.environ["pychemqt"]+"dat"+os.sep+"mEoS" + \
            os.sep + self.filename+".gz"
        filenameSoft = config.conf_dir+self.filename
        if os.path.isfile(filenameSoft):
            print(filenameSoft)
            with open(filenameSoft, "rb") as archivo:
                data = pickle.load(archivo, fix_imports=False, errors="strict")
            return data
        elif os.path.isfile(filenameHard):
            print(filenameHard)
            with gzip.GzipFile(filenameHard, 'rb') as archivo:
                data = pickle.load(archivo, encoding="latin1")
            self._saveData(data)
            return data

    def _saveData(self, data):
        """Save changes in data to file"""
        with open(config.conf_dir+self.filename, 'wb') as file:
            pickle.dump(data, file)

    def click(self, event):
        """Update input and graph annotate when mouse click over chart"""
        # Accept only left click
        print(event, self.x, self.y)
        if event.button != 1:
            return
        units = {"x": unidades.Dimensionless,
                 "T": unidades.Temperature,
                 "P": unidades.Pressure,
                 "h": unidades.Enthalpy,
                 "u": unidades.Enthalpy,
                 "s": unidades.SpecificHeat,
                 "v": unidades.SpecificVolume,
                 "rho": unidades.Density}
        if self.x in units and self.y in units:
            x = units[self.x](event.xdata, "conf")
            y = units[self.y](event.ydata, "conf")

            fluid = mEoS.__all__[self.config["fluid"]]
            kwargs = {self.x: x, self.y: y}
            print(fluid, self.config, kwargs)
            fluido = calcPoint(fluid, self.config, **kwargs)
            if fluido and fluido.status and \
                    fluido._constants["Tmin"] <= fluido.T and \
                    fluido.T <= fluido._constants["Tmax"] and \
                    0 < fluido.P.kPa and \
                    fluido.P.kPa <= fluido._constants["Pmax"]:
                self.plot.lx.set_ydata(event.ydata)
                self.plot.ly.set_xdata(event.xdata)
                self.plot.lx.set_visible(True)
                self.plot.ly.set_visible(True)
                self.showPointData(fluido)
            else:
                self.plot.lx.set_visible(False)
                self.plot.ly.set_visible(False)
                self.clearPointData()

    def showPointData(self, state):
        self.clearPointData()
        yi = 0.98
        for key in ("T", "P", "x", "v", "rho", "h", "s", "u"):
            self.notes.append(self.plot.ax.annotate(
                "%s: %s" % (key, state.__getattribute__(key).str), (0.01, yi),
                xycoords='axes fraction', size="small", va="center"))
            yi -= 0.025
        self.plot.draw()

    def clearPointData(self):
        while self.notes:
            anotation = self.notes.pop()
            anotation.remove()
        self.plot.draw()

    def writeToJSON(self, data):
        """Write instance parameter to file"""
        data["filename"] = self.filename
        data["windowTitle"] = self.windowTitle()
        data["x"] = self.x
        data["y"] = self.y
        data["z"] = self.z

        # TODO: Add support for save font properties
        # Title format
        title = {}
        title["txt"] = self.plot.ax.get_title()
        title["color"] = self.plot.ax.title.get_color()
        title["family"] = self.plot.ax.title.get_fontfamily()
        title["style"] = self.plot.ax.title.get_style()
        title["weight"] = self.plot.ax.title.get_weight()
        title["stretch"] = self.plot.ax.title.get_stretch()
        title["size"] = self.plot.ax.title.get_size()
        data["title"] = title

        # xlabel format
        xlabel = {}
        xlabel["txt"] = self.plot.ax.get_xlabel()
        xlabel["color"] = self.plot.ax.xaxis.get_label().get_color()
        xlabel["family"] = self.plot.ax.xaxis.get_label().get_fontfamily()
        xlabel["style"] = self.plot.ax.xaxis.get_label().get_style()
        xlabel["weight"] = self.plot.ax.xaxis.get_label().get_weight()
        xlabel["stretch"] = self.plot.ax.xaxis.get_label().get_stretch()
        xlabel["size"] = self.plot.ax.xaxis.get_label().get_size()
        data["xlabel"] = xlabel

        # ylable format
        ylabel = {}
        ylabel["txt"] = self.plot.ax.get_ylabel()
        ylabel["color"] = self.plot.ax.yaxis.get_label().get_color()
        ylabel["family"] = self.plot.ax.yaxis.get_label().get_fontfamily()
        ylabel["style"] = self.plot.ax.yaxis.get_label().get_style()
        ylabel["weight"] = self.plot.ax.yaxis.get_label().get_weight()
        ylabel["stretch"] = self.plot.ax.yaxis.get_label().get_stretch()
        ylabel["size"] = self.plot.ax.yaxis.get_label().get_size()
        data["ylabel"] = ylabel

        # zlable format
        zlabel = {}
        if self.z:
            zlabel["txt"] = self.plot.ax.get_zlabel()
            zlabel["color"] = self.plot.ax.zaxis.get_label().get_color()
            zlabel["family"] = self.plot.ax.zaxis.get_label().get_fontfamily()
            zlabel["style"] = self.plot.ax.zaxis.get_label().get_style()
            zlabel["weight"] = self.plot.ax.zaxis.get_label().get_weight()
            zlabel["stretch"] = self.plot.ax.zaxis.get_label().get_stretch()
            zlabel["size"] = self.plot.ax.zaxis.get_label().get_size()
        data["zlabel"] = zlabel

        data["grid"] = self.plot.ax._gridOn
        data["xscale"] = self.plot.ax.get_xscale()
        data["yscale"] = self.plot.ax.get_yscale()
        xmin, xmax = self.plot.ax.get_xlim()
        data["xmin"] = xmin
        data["xmax"] = xmax
        ymin, ymax = self.plot.ax.get_ylim()
        data["ymin"] = ymin
        data["ymax"] = ymax
        if self.z:
            zmin, zmax = self.plot.ax.get_zlim()
            data["zmin"] = zmin
            data["zmax"] = zmax
        else:
            data["zmin"] = None
            data["zmax"] = None

        data["marginleft"] = self.plot.fig.subplotpars.left
        data["marginbottom"] = self.plot.fig.subplotpars.bottom
        data["marginright"] = self.plot.fig.subplotpars.right
        data["margintop"] = self.plot.fig.subplotpars.top

        # Config
        data["fluid"] = self.config["fluid"]
        data["eq"] = self.config["eq"]
        data["visco"] = self.config["visco"]
        data["thermal"] = self.config["thermal"]

        # data
        lines = {}
        for line in self.plot.ax.lines[2:]:
            dat = {}
            dat["x"] = list(line.get_xdata())
            dat["y"] = list(line.get_ydata())
            dat["label"] = line.get_label()

            # line style
            dat["lw"] = line.get_lw()
            dat["ls"] = line.get_ls()
            dat["marker"] = line.get_marker()
            dat["color"] = line.get_color()
            dat["ms"] = line.get_ms()
            dat["mfc"] = line.get_mfc()
            dat["mew"] = line.get_mew()
            dat["mec"] = line.get_mec()
            dat["visible"] = line.get_visible()
            dat["antialiased"] = line.get_antialiased()

            # line text
            # saturation and melting line dont define it at plot creation
            try:
                text = {}
                text["visible"] = line.text.get_visible()
                text["txt"] = line.text.get_text()
                text["rot"] = line.text.get_rotation()
                text["pos"] = line.text.pos
                text["family"] = line.text.get_fontfamily()
                text["style"] = line.text.get_style()
                text["weight"] = line.text.get_weight()
                text["stretch"] = line.text.get_stretch()
                text["size"] = line.text.get_size()
                text["va"] = line.text.get_va()
            except AttributeError:
                text = {"visible": False, "txt": "", "pos": 50, "rot": 0,
                        "family": "sans-serif", "style": "normal",
                        "weight": "normal", "stretch": "normal",
                        "size": "small", "va": "center"}
            dat["annotation"] = text

            lines[line._label] = dat
        data["lines"] = lines

    @classmethod
    def readFromJSON(cls, data, parent):
        filename = data["filename"]
        title = data["windowTitle"]
        x = data["x"]
        y = data["y"]
        z = data["z"]
        if z:
            dim = 3
        else:
            dim = 2
        grafico = PlotMEoS(dim=dim, parent=parent, filename=filename)
        grafico.x = x
        grafico.y = y
        grafico.z = z
        grafico.setWindowTitle(title)

        title = data["title"]["txt"]
        if title:
            grafico.plot.ax.set_title(title)
            grafico.plot.ax.title.set_color(data["title"]["color"])
            grafico.plot.ax.title.set_family(data["title"]["family"])
            grafico.plot.ax.title.set_style(data["title"]["style"])
            grafico.plot.ax.title.set_weight(data["title"]["weight"])
            grafico.plot.ax.title.set_stretch(data["title"]["stretch"])
            grafico.plot.ax.title.set_size(data["title"]["size"])

        xlabel = data["xlabel"]["txt"]
        if xlabel:
            grafico.plot.ax.set_xlabel(xlabel)
            label = grafico.plot.ax.xaxis.get_label()
            label.set_color(data["xlabel"]["color"])
            label.set_family(data["xlabel"]["family"])
            label.set_style(data["xlabel"]["style"])
            label.set_weight(data["xlabel"]["weight"])
            label.set_stretch(data["xlabel"]["stretch"])
            label.set_size(data["xlabel"]["size"])

        ylabel = data["ylabel"]["txt"]
        if ylabel:
            grafico.plot.ax.set_ylabel(ylabel)
            label = grafico.plot.ax.yaxis.get_label()
            label.set_color(data["ylabel"]["color"])
            label.set_family(data["ylabel"]["family"])
            label.set_style(data["ylabel"]["style"])
            label.set_weight(data["ylabel"]["weight"])
            label.set_stretch(data["ylabel"]["stretch"])
            label.set_size(data["ylabel"]["size"])

        if z:
            zlabel = data["zlabel"]["txt"]
            if zlabel:
                grafico.plot.ax.set_zlabel(zlabel)
                label = grafico.plot.ax.zaxis.get_label()
                label.set_color(data["zlabel"]["color"])
                label.set_family(data["zlabel"]["family"])
                label.set_style(data["zlabel"]["style"])
                label.set_weight(data["zlabel"]["weight"])
                label.set_stretch(data["zlabel"]["stretch"])
                label.set_size(data["zlabel"]["size"])

        grafico.plot.ax._gridOn = data["grid"]
        grafico.plot.ax.grid(data["grid"])

        grafico.plot.ax.set_xlim(data["xmin"], data["xmax"])
        grafico.plot.ax.set_ylim(data["ymin"], data["ymax"])
        if z:
            grafico.plot.ax.set_zlim(data["zmin"], data["zmax"])

        for label, line in data["lines"].items():
            x = line["x"]
            y = line["y"]

            format = {}
            format["lw"] = line["lw"]
            format["ls"] = line["ls"]
            format["marker"] = line["marker"]
            format["color"] = line["color"]
            format["ms"] = line["ms"]
            format["mfc"] = line["mfc"]
            format["mew"] = line["mew"]
            format["mec"] = line["mec"]

            ln, = grafico.plot.ax.plot(x, y, label=label, **format)
            ln.set_visible(line["visible"])
            ln.set_antialiased(line["antialiased"])

            txt = line["annotation"]["txt"]
            rot = line["annotation"]["rot"]
            pos = line["annotation"]["pos"]
            i = int(len(x)*pos/100)
            kw = {}
            kw["ha"] = "center"
            kw["rotation_mode"] = "anchor"
            for key in ("va", "visible", "family", "style", "weight",
                        "stretch", "size"):
                kw[key] = line["annotation"][key]

            if i >= len(x):
                i = len(x)-1
            text = grafico.plot.ax.text(x[i], y[i], txt, rotation=rot, **kw)

            # We creating a link between line and its annotation text
            ln.text = text
            # We save position value in % unit to avoid index find
            ln.text.pos = pos

        grafico.plot.ax.set_xscale(data["xscale"])
        grafico.plot.ax.set_yscale(data["yscale"])

        # Load margins
        left = data["marginleft"]
        bottom = data["marginbottom"]
        right = data["marginright"]
        top = data["margintop"]
        grafico.plot.fig.subplots_adjust(left, bottom, right, top)

        # Load config
        conf = {}
        conf["fluid"] = data["fluid"]
        conf["eq"] = data["eq"]
        conf["visco"] = data["visco"]
        conf["thermal"] = data["thermal"]
        grafico.config = conf

        return grafico


class Plot2D(QtWidgets.QDialog):
    """Dialog for select a special 2D plot"""
    def __init__(self, parent=None):
        super(Plot2D, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Setup 2D Plot"))
        layout = QtWidgets.QVBoxLayout(self)
        group_Ejex = QtWidgets.QGroupBox(
            QtWidgets.QApplication.translate("pychemqt", "Axis X"))
        layout.addWidget(group_Ejex)
        layout_GroupX = QtWidgets.QVBoxLayout(group_Ejex)
        self.ejeX = QtWidgets.QComboBox()
        layout_GroupX.addWidget(self.ejeX)
        self.Xscale = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Logarithmic scale"))
        layout_GroupX.addWidget(self.Xscale)
        for prop in ThermoAdvanced.propertiesName():
            self.ejeX.addItem(prop)

        group_Ejey = QtWidgets.QGroupBox(
            QtWidgets.QApplication.translate("pychemqt", "Axis Y"))
        layout.addWidget(group_Ejey)
        layout_GroupY = QtWidgets.QVBoxLayout(group_Ejey)
        self.ejeY = QtWidgets.QComboBox()
        layout_GroupY.addWidget(self.ejeY)
        self.Yscale = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Logarithmic scale"))
        layout_GroupY.addWidget(self.Yscale)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.ejeXChanged(0)
        self.ejeX.currentIndexChanged.connect(self.ejeXChanged)

    def ejeXChanged(self, index):
        """Fill variables available in ejeY, all except the active in ejeX"""
        # Save current status to restore
        current = self.ejeY.currentIndex()
        if current == -1:
            current = 0

        # Refill ejeY combo
        self.ejeY.clear()
        props = ThermoAdvanced.propertiesName()
        del props[index]
        for prop in props:
            self.ejeY.addItem(prop)

        # Restore inicial state
        if index == 0 and current == 0:
            self.ejeY.setCurrentIndex(0)
        elif index <= current:
            self.ejeY.setCurrentIndex(current)
        else:
            self.ejeY.setCurrentIndex(current+1)


class Plot3D(QtWidgets.QDialog):
    """Dialog for configure a 3D plot"""

    def __init__(self, parent=None):
        super(Plot3D, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Setup 3D Plot"))
        layout = QtWidgets.QGridLayout(self)

        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Axis X")), 1, 1)
        self.ejeX = QtWidgets.QComboBox()
        for prop in ThermoAdvanced.propertiesName():
            self.ejeX.addItem(prop)
        layout.addWidget(self.ejeX, 1, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Axis Y")), 2, 1)
        self.ejeY = QtWidgets.QComboBox()
        layout.addWidget(self.ejeY, 2, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Axis Z")), 3, 1)
        self.ejeZ = QtWidgets.QComboBox()
        layout.addWidget(self.ejeZ, 3, 2)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 4, 1, 1, 2)

        self.ejeX.currentIndexChanged.connect(self.ejeXChanged)
        self.ejeY.currentIndexChanged.connect(self.ejeYChanged)
        self.ejeXChanged(0)

    def ejeXChanged(self, index):
        """Fill variables available in ejeY, all except the active in ejeX"""
        # Save current status to restore
        current = self.ejeY.currentIndex()
        if current == -1:
            current = 0

        # Refill ejeY combo
        self.ejeY.clear()
        props = ThermoAdvanced.propertiesName()
        del props[index]
        for prop in props:
            self.ejeY.addItem(prop)

        # Restore inicial state
        if index == 0 and current == 0:
            self.ejeY.setCurrentIndex(0)
        elif index <= current:
            self.ejeY.setCurrentIndex(current)
        else:
            self.ejeY.setCurrentIndex(current+1)

    def ejeYChanged(self, indY):
        """Fill variables available in ejeZ, all except the actives in other"""
        # Save current status to restore
        current = self.ejeZ.currentIndex()
        if current == -1:
            current = 0

        # Refill ejeY combo
        self.ejeZ.clear()
        prop2 = ThermoAdvanced.propertiesName()[:]
        indX = self.ejeX.currentIndex()
        del prop2[indX]
        del prop2[indY]
        for prop in prop2:
            self.ejeZ.addItem(prop)

        # Restore inicial state
        if indX == 0 and indY == 0 and current == 0:
            self.ejeZ.setCurrentIndex(0)
        elif indY <= current or indX <= current:
            self.ejeZ.setCurrentIndex(current)
        else:
            self.ejeZ.setCurrentIndex(current+1)


class EditPlot(QtWidgets.QWidget):
    """Dialog to edit plot. This dialog let user change plot p"""
    def __init__(self, plotMEoS, mainwindow, parent=None):
        super(EditPlot, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Edit Plot"))
        layout = QtWidgets.QGridLayout(self)
        self.plotMEoS = plotMEoS
        self.fig = plotMEoS.plot
        self.mainwindow = mainwindow

        self.lista = QtWidgets.QListWidget()
        layout.addWidget(self.lista, 0, 1, 1, 3)

        lytTitle = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Label"))
        lytTitle.addWidget(label)
        self.label = QtWidgets.QLineEdit()
        lytTitle.addWidget(self.label)
        layout.addLayout(lytTitle, 1, 1, 1, 3)

        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Line Width")), 2, 1)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Line Style")), 2, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Color")), 2, 3)
        self.Grosor = QtWidgets.QDoubleSpinBox()
        self.Grosor.setAlignment(QtCore.Qt.AlignRight)
        self.Grosor.setRange(0.1, 5)
        self.Grosor.setDecimals(1)
        self.Grosor.setSingleStep(0.1)
        layout.addWidget(self.Grosor, 3, 1)
        self.Linea = LineStyleCombo()
        layout.addWidget(self.Linea, 3, 2)
        self.ColorButton = ColorSelector()
        layout.addWidget(self.ColorButton, 3, 3)

        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Marker")), 4, 1)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Marker Size")), 4, 2)
        layout.addWidget(QtWidgets.QLabel(QtWidgets.QApplication.translate(
            "pychemqt", "Marker Color")), 4, 3)
        self.Marca = MarkerCombo()
        layout.addWidget(self.Marca, 5, 1)
        self.markerSize = QtWidgets.QDoubleSpinBox()
        self.markerSize.setAlignment(QtCore.Qt.AlignRight)
        self.markerSize.setDecimals(1)
        self.markerSize.setSingleStep(0.1)
        layout.addWidget(self.markerSize, 5, 2)
        self.markerfacecolor = ColorSelector()
        layout.addWidget(self.markerfacecolor, 5, 3)

        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Marker edge")), 7, 1)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Width")), 6, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Color")), 6, 3)
        self.markerEdgeSize = QtWidgets.QDoubleSpinBox()
        self.markerEdgeSize.setAlignment(QtCore.Qt.AlignRight)
        self.markerEdgeSize.setDecimals(1)
        self.markerEdgeSize.setSingleStep(0.1)
        layout.addWidget(self.markerEdgeSize, 7, 2)
        self.markeredgecolor = ColorSelector()
        layout.addWidget(self.markeredgecolor, 7, 3)

        grpAnnotate = QtWidgets.QGroupBox(
            QtWidgets.QApplication.translate("pychemqt", "Annotation"))
        layout.addWidget(grpAnnotate, 8, 1, 1, 3)
        lytAnnotation = QtWidgets.QGridLayout(grpAnnotate)
        self.annotationVisible = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Visible"))
        lytAnnotation.addWidget(self.annotationVisible, 1, 1, 1, 3)

        lytTitle = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Label"))
        lytTitle.addWidget(label)
        # self.annotationLabel = QtWidgets.QLineEdit()
        self.annotationLabel = InputFont()
        lytTitle.addWidget(self.annotationLabel)
        lytAnnotation.addLayout(lytTitle, 2, 1, 1, 3)

        lytPosition = QtWidgets.QHBoxLayout()
        lytPosition.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Location")))
        self.labelAnnotationPos = Entrada_con_unidades(
            int, value=50, width=40, frame=False, readOnly=True, suffix="%",
            showNull=True)
        self.labelAnnotationPos.setFixedWidth(40)
        lytPosition.addWidget(self.labelAnnotationPos)
        self.annotationPos = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.annotationPos.setRange(0, 100)
        self.annotationPos.setValue(50)
        self.annotationPos.valueChanged.connect(
            partial(self._updateLabel, self.labelAnnotationPos))
        lytPosition.addWidget(self.annotationPos)
        lytAnnotation.addLayout(lytPosition, 3, 1, 1, 3)

        lytAngle = QtWidgets.QHBoxLayout()
        lytAngle.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Rotation")))
        self.labelAnnotationRot = Entrada_con_unidades(
            int, value=50, width=40, frame=False, readOnly=True, suffix="º",
            showNull=True)
        self.labelAnnotationRot.setFixedWidth(40)
        lytAngle.addWidget(self.labelAnnotationRot)
        self.annotationRot = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.annotationRot.setRange(0, 360)
        self.annotationRot.setValue(0)
        self.annotationRot.valueChanged.connect(
            partial(self._updateLabel, self.labelAnnotationRot))
        lytAngle.addWidget(self.annotationRot)
        lytAnnotation.addLayout(lytAngle, 4, 1, 1, 3)

        lytVA = QtWidgets.QHBoxLayout()
        lytVA.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Aligment")))
        self.annotationVA = QtWidgets.QComboBox()
        alignment = [
            QtWidgets.QApplication.translate("pychemqt", "Center"),
            QtWidgets.QApplication.translate("pychemqt", "Top"),
            QtWidgets.QApplication.translate("pychemqt", "Bottom"),
            QtWidgets.QApplication.translate("pychemqt", "Baseline"),
            QtWidgets.QApplication.translate("pychemqt", "Center baseline")]
        for alig in alignment:
            self.annotationVA.addItem(alig)
        lytVA.addWidget(self.annotationVA)
        lytVA.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding))
        lytAnnotation.addLayout(lytVA, 5, 1, 1, 3)

        self.annotationVisible.stateChanged.connect(
            self.annotationLabel.setEnabled)
        self.annotationVisible.stateChanged.connect(
            self.annotationPos.setEnabled)
        self.annotationVisible.stateChanged.connect(
            self.annotationRot.setEnabled)

        self.visible = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Visible"))
        layout.addWidget(self.visible, 13, 1, 1, 3)
        self.antialiases = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Antialiases"))
        layout.addWidget(self.antialiases, 14, 1, 1, 3)

        layoutButton = QtWidgets.QHBoxLayout()
        layout.addLayout(layoutButton, 15, 1, 1, 3)
        self.botonAdd = QtWidgets.QPushButton(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] + "/images/button/add.png")), "")
        self.botonAdd.clicked.connect(self.add)
        layoutButton.addWidget(self.botonAdd)
        self.botonRemove = QtWidgets.QPushButton(QtGui.QIcon(QtGui.QPixmap(
            os.environ["pychemqt"] + "/images/button/remove.png")), "")
        self.botonRemove.clicked.connect(self.remove)
        layoutButton.addWidget(self.botonRemove)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close)
        self.buttonBox.rejected.connect(self.close)
        layoutButton.addWidget(self.buttonBox)

        for linea in self.fig.ax.lines[2:]:
            self.lista.addItem(linea._label)

        self.lista.currentRowChanged.connect(self.update)
        self.label.textChanged.connect(partial(self.changeValue, "label"))
        self.Grosor.valueChanged.connect(partial(self.changeValue, "lw"))
        self.Linea.valueChanged.connect(partial(self.changeValue, "ls"))
        self.Linea.currentIndexChanged.connect(self.ColorButton.setEnabled)
        self.ColorButton.valueChanged.connect(
            partial(self.changeValue, "color"))
        self.Marca.valueChanged.connect(partial(self.changeValue, "marker"))
        self.Marca.currentIndexChanged.connect(self.markerSize.setEnabled)
        self.Marca.currentIndexChanged.connect(self.markerfacecolor.setEnabled)
        self.Marca.currentIndexChanged.connect(self.markerEdgeSize.setEnabled)
        self.Marca.currentIndexChanged.connect(self.markeredgecolor.setEnabled)
        self.markerSize.valueChanged.connect(partial(self.changeValue, "ms"))
        self.markerfacecolor.valueChanged.connect(
            partial(self.changeValue, "mfc"))
        self.markerEdgeSize.valueChanged.connect(
            partial(self.changeValue, "mew"))
        self.markeredgecolor.valueChanged.connect(
            partial(self.changeValue, "mec"))
        self.visible.toggled.connect(partial(self.changeValue, "visible"))
        self.antialiases.toggled.connect(
            partial(self.changeValue, "antialiases"))

        self.annotationVisible.toggled.connect(
            partial(self.changeValue, "textVisible"))
        self.annotationLabel.textChanged.connect(
            partial(self.changeValue, "textLabel"))
        self.annotationLabel.colorChanged.connect(
                partial(self.changeValue, "textcolor"))
        self.annotationLabel.fontChanged.connect(
            partial(self.changeValue, "textfont"))
        self.annotationPos.valueChanged.connect(
            partial(self.changeValue, "textPos"))
        self.annotationRot.valueChanged.connect(
            partial(self.changeValue, "textRot"))
        self.annotationVA.currentIndexChanged.connect(
            partial(self.changeValue, "textVA"))
        self.lista.setCurrentRow(0)

    def _updateLabel(self, label, value):
        label.setValue(value)

    def update(self, i):
        """Fill format widget with value of selected line"""
        linea = self.fig.ax.lines[i+2]
        self.label.setText(linea.get_label())
        self.Grosor.setValue(linea.get_lw())
        self.Linea.setCurrentValue(linea.get_ls())
        self.ColorButton.setColor(linea.get_color())
        self.Marca.setCurrentValue(linea.get_marker())
        self.Marca.currentIndexChanged.emit(self.Marca.currentIndex())
        self.markerSize.setValue(linea.get_ms())
        self.markerfacecolor.setColor(linea.get_mfc())
        self.markerEdgeSize.setValue(linea.get_mew())
        self.markeredgecolor.setColor(linea.get_mec())
        self.visible.setChecked(linea.get_visible())
        self.antialiases.setChecked(linea.get_antialiased())

        try:
            self.annotationVisible.setChecked(linea.text.get_visible())
            self.annotationLabel.setText(linea.text.get_text())
            self.annotationPos.setValue(linea.text.pos)
            self.annotationRot.setValue(linea.text.get_rotation())
            va = ["center", "top", "bottom", "baseline", "center_baseline"]
            self.annotationVA.setCurrentIndex(va.index(linea.text.get_va()))
        except AttributeError:
            self.annotationVisible.setChecked(False)

    def changeValue(self, key, value):
        """Update plot data"""
        linea = self.fig.ax.lines[self.lista.currentRow()+2]
        func = {"label": linea.set_label,
                "lw": linea.set_lw,
                "ls": linea.set_ls,
                "marker": linea.set_marker,
                "color": linea.set_color,
                "ms": linea.set_ms,
                "mfc": linea.set_mfc,
                "mew": linea.set_mew,
                "mec": linea.set_mec,
                "visible": linea.set_visible,
                "antialiases": linea.set_antialiased,
                "textVisible": linea.text.set_visible,
                "textLabel": linea.text.set_text,
                "textcolor": linea.text.set_color,
                "textfont": linea.text.set_fontproperties,
                "textPos": linea.text.set_position,
                "textRot": linea.text.set_rotation,
                "textVA": linea.text.set_va}

        if key == "textPos":
            linea.text.pos = value
            xi = linea.get_xdata()
            yi = linea.get_ydata()
            i = int(len(xi)*value/100)
            if i >= len(xi):
                i = len(yi)-1
            value = xi[i], yi[i]
        elif key == "textVA":
            va = ["center", "top", "bottom", "baseline", "center_baseline"]
            value = va[value]
        elif key == "textfont":
            value = convertFont(value)
        elif key in ("ls", "marker", "color", "mfc", "mec"):
            value = str(value)
        func[key](value)
        if key == "label":
            self.lista.currentItem().setText(value)
        else:
            self.fig.draw()

    def add(self):
        """Add a isoline to plot"""
        dialog = AddLine()
        if dialog.exec_():
            points = get_points(config.Preferences)
            self.mainwindow.progressBar.setVisible(True)
            index = self.mainwindow.currentConfig.getint("MEoS", "fluid")
            # fluid = getClassFluid(self.config)
            fluid = mEoS.__all__[index]
            prop = dialog.tipo.currentIndex()
            value = dialog.input[prop].value

            eq = fluid.eq[self.mainwindow.currentConfig.getint("MEoS", "eq")]
            T = list(concatenate([
                linspace(eq["Tmin"], 0.9*fluid.Tc, points),
                linspace(0.9*fluid.Tc, 0.99*fluid.Tc, points),
                linspace(0.99*fluid.Tc, fluid.Tc, points),
                linspace(fluid.Tc, 1.01*fluid.Tc, points),
                linspace(1.01*fluid.Tc, 1.1*fluid.Tc, points),
                linspace(1.1*fluid.Tc, eq["Tmax"], points)]))

            Pmin = fluid(T=eq["Tmin"], x=0).P
            Pmax = eq["Pmax"]*1000
            P = list(concatenate([
                logspace(log10(Pmin), log10(0.9*fluid.Pc), points),
                linspace(0.9*fluid.Pc, 0.99*fluid.Pc, points),
                linspace(0.99*fluid.Pc, fluid.Pc, points),
                linspace(fluid.Pc, 1.01*fluid.Pc, points),
                linspace(1.01*fluid.Pc, 1.1*fluid.Pc, points),
                logspace(log10(1.1*fluid.Pc), log10(Pmax), points)]))
            for i in range(5, 0, -1):
                del T[points*i]
                del P[points*i]

            if prop == 0:
                # Calcualte isotherm line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isotherm line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "P", "T", P, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "T"
                name = "Isotherm"
                unit = unidades.Temperature
            elif prop == 1:
                # Calculate isobar line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isobar line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "T", "P", T, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "P"
                name = "Isobar"
                unit = unidades.Pressure
            elif prop == 2:
                # Calculate isoenthalpic line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isoenthalpic line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "P", "h", P, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "h"
                name = "Isoenthalpic"
                unit = unidades.Enthalpy
            elif prop == 3:
                # Calculate isoentropic line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isoentropic line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "T", "s", T, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "s"
                name = "Isoentropic"
                unit = unidades.SpecificHeat
            elif prop == 4:
                # Calculate isochor line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isochor line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "T", "v", T, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "v"
                name = "Isochor"
                unit = unidades.SpecificVolume
            elif prop == 5:
                # Calculate isodensity line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isodensity line..."))
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "T", "rho", T, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "rho"
                name = "Isochor"
                unit = unidades.Density
            elif prop == 6:
                # Calculate isoquality line
                self.mainwindow.statusbar.showMessage(
                    QtWidgets.QApplication.translate(
                        "pychemqt", "Adding isoquality line..."))
                T = T[:3*points-2]
                fluidos = calcIsoline(
                    fluid, self.mainwindow.currentConfig, "T", "x", T, value,
                    0, 0, 100, 1, self.mainwindow.progressBar)
                var = "x"
                name = "Isoquality"
                unit = unidades.Dimensionless

            line = {value: {}}
            for x in ThermoAdvanced.propertiesKey():
                dat_propiedad = []
                for fluido in fluidos:
                    num = fluido.__getattribute__(x)
                    if isinstance(num, str):
                        dat_propiedad.append(num)
                    elif x in ("f", "fi"):
                        dat_propiedad.append(num[0])
                    elif num is not None:
                        dat_propiedad.append(num._data)
                    else:
                        dat_propiedad.append(None)
                line[value][x] = dat_propiedad

            style = getLineFormat(config.Preferences, name)
            functionx = _getunitTransform(self.plotMEoS.x)
            functiony = _getunitTransform(self.plotMEoS.y)
            functionz = _getunitTransform(self.plotMEoS.z)
            transform = (functionx, functiony, functionz)
            ax = self.plotMEoS.x, self.plotMEoS.y, self.plotMEoS.z
            plotIsoline(line, ax, var, unit, self.plotMEoS, transform, **style)

            self.plotMEoS.plot.draw()
            self.mainwindow.progressBar.setVisible(False)
            self.lista.addItem(self.fig.ax.lines[-1].get_label())
            self.lista.setCurrentRow(self.lista.count()-1)

            # Save new line to file
            data = self.plotMEoS._getData()
            if var not in data:
                data[var] = {}
            data[var][value] = line[value]
            self.plotMEoS._saveData(data)

    def remove(self):
        """Remove a line from plot"""
        self.mainwindow.statusbar.showMessage(QtWidgets.QApplication.translate(
            "pychemqt", "Deleting line..."))
        QtWidgets.QApplication.processEvents()

        # Remove data from file
        data = self.plotMEoS._getData()
        txt = self.lista.currentItem().text().split()
        var = txt[0]
        units = {"T": unidades.Temperature,
                 "P": unidades.Pressure,
                 "v": unidades.SpecificVolume,
                 "rho": unidades.Density,
                 "h": unidades.Enthalpy,
                 "s": unidades.SpecificHeat,
                 "x": unidades.Dimensionless}
        if var in units:
            unit = units[var]
            for key in data[var]:
                str = unit(key).str
                if str[1:] == " ".join(txt[2:]):
                    del data[var][key]
                    self.plotMEoS._saveData(data)
                    break

        # Remove line to plot and update list element
        index = self.lista.currentRow()
        del self.fig.ax.lines[index+2]
        if index == 0:
            self.lista.setCurrentRow(1)
        else:
            self.lista.setCurrentRow(index-1)
        self.lista.takeItem(index)
        self.fig.draw()
        self.mainwindow.statusbar.clearMessage()


class AddLine(QtWidgets.QDialog):
    """Dialog to add new isoline to plot"""
    lineas = [(QtWidgets.QApplication.translate("pychemqt", "Isotherm"),
               unidades.Temperature, None),
              (QtWidgets.QApplication.translate("pychemqt", "Isobar"),
               unidades.Pressure, None),
              (QtWidgets.QApplication.translate("pychemqt", "Isoenthalpic"),
               unidades.Enthalpy, None),
              (QtWidgets.QApplication.translate("pychemqt", "Isoentropic"),
              unidades.SpecificHeat, "SpecificEntropy"),
              (QtWidgets.QApplication.translate("pychemqt", "Isochor"),
              unidades.SpecificVolume, None),
              (QtWidgets.QApplication.translate("pychemqt", "Isodensity"),
              unidades.Density, None),
              (QtWidgets.QApplication.translate("pychemqt", "Isoquality"),
              float, None)]

    def __init__(self, parent=None):
        super(AddLine, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Add Line to Plot"))
        layout = QtWidgets.QGridLayout(self)

        self.tipo = QtWidgets.QComboBox()
        layout.addWidget(self.tipo, 1, 1, 1, 2)
        layout.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Value")), 2, 1)

        self.input = []
        for title, unidad, magnitud in self.lineas:
            self.input.append(Entrada_con_unidades(unidad, magnitud))
            layout.addWidget(self.input[-1], 2, 2)
            self.tipo.addItem(title)

        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 10, 1, 1, 2)

        self.isolineaChanged(0)
        self.tipo.currentIndexChanged.connect(self.isolineaChanged)

    def isolineaChanged(self, int):
        """Let show only the active inputs"""
        for i in self.input:
            i.setVisible(False)
        self.input[int].setVisible(True)


class EditAxis(QtWidgets.QDialog):
    """Dialog to configure axes plot properties, label, margins, scales"""
    def __init__(self, fig=None, parent=None):
        super(EditAxis, self).__init__(parent)
        self.setWindowTitle(
            QtWidgets.QApplication.translate("pychemqt", "Edit Axis"))
        layout = QtWidgets.QGridLayout(self)
        self.fig = fig

        lytTitle = QtWidgets.QHBoxLayout()
        lb = QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Title"))
        lb.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        lytTitle.addWidget(lb)
        self.title = InputFont()
        lytTitle.addWidget(self.title)
        layout.addLayout(lytTitle, 1, 1, 1, self.fig.dim)

        self.axisX = AxisWidget("x", self)
        layout.addWidget(self.axisX, 2, 1)
        self.axisY = AxisWidget("y", self)
        layout.addWidget(self.axisY, 2, 2)

        if self.fig.dim == 3:
            self.axisZ = AxisWidget("z", self)
            layout.addWidget(self.axisZ, 2, 3)
            self.axisX.scale.setEnabled(False)
            self.axisY.scale.setEnabled(False)
            self.axisZ.scale.setEnabled(False)

        self.gridCheckbox = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Show Grid"))
        layout.addWidget(self.gridCheckbox, 3, 1, 1, self.fig.dim)
        layout.addItem(QtWidgets.QSpacerItem(
            10, 10, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding), 5, 1, 1, self.fig.dim)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 10, 1, 1, self.fig.dim)

        if fig:
            self.populate()

        self.title.textChanged.connect(partial(self.update, "title"))
        self.title.colorChanged.connect(partial(self.update, "titlecolor"))
        self.title.fontChanged.connect(partial(self.update, "titlefont"))
        self.axisX.label.textChanged.connect(partial(self.update, "xlabel"))
        self.axisX.label.colorChanged.connect(
            partial(self.update, "xlabelcolor"))
        self.axisX.label.fontChanged.connect(
            partial(self.update, "xlabelfont"))
        self.axisY.label.textChanged.connect(partial(self.update, "ylabel"))
        self.axisY.label.colorChanged.connect(
            partial(self.update, "ylabelcolor"))
        self.axisY.label.fontChanged.connect(
            partial(self.update, "ylabelfont"))
        self.gridCheckbox.toggled.connect(partial(self.update, "grid"))
        self.axisX.scale.toggled.connect(partial(self.update, "xscale"))
        self.axisY.scale.toggled.connect(partial(self.update, "yscale"))
        self.axisX.min.valueChanged.connect(partial(self.update, "xmin"))
        self.axisY.min.valueChanged.connect(partial(self.update, "ymin"))
        self.axisX.max.valueChanged.connect(partial(self.update, "xmax"))
        self.axisY.max.valueChanged.connect(partial(self.update, "ymax"))
        if self.fig.dim == 3:
            self.axisZ.label.textChanged.connect(
                partial(self.update, "zlabel"))
            self.axisZ.label.colorChanged.connect(
                partial(self.update, "zlabelcolor"))
            self.axisZ.label.fontChanged.connect(
                partial(self.update, "zlabelfont"))
            self.axisZ.min.valueChanged.connect(partial(self.update, "zmin"))
            self.axisZ.max.valueChanged.connect(partial(self.update, "zmax"))

    def populate(self):
        """Fill widget with plot parameters"""
        self.title.setText(self.fig.ax.get_title())
        self.title.setColor(QtGui.QColor(self.fig.ax.title.get_color()))
        self.axisX.label.setText(self.fig.ax.get_xlabel())
        xcolor = self.fig.ax.xaxis.get_label().get_color()
        self.axisX.label.setColor(QtGui.QColor(xcolor))
        self.axisY.label.setText(self.fig.ax.get_ylabel())
        ycolor = self.fig.ax.yaxis.get_label().get_color()
        self.axisY.label.setColor(QtGui.QColor(ycolor))
        self.gridCheckbox.setChecked(self.fig.ax._gridOn)
        self.axisX.scale.setChecked(self.fig.ax.get_xscale() == "log")
        self.axisY.scale.setChecked(self.fig.ax.get_yscale() == "log")
        xmin, xmax = self.fig.ax.get_xlim()
        self.axisX.min.setValue(xmin)
        self.axisX.max.setValue(xmax)
        ymin, ymax = self.fig.ax.get_ylim()
        self.axisY.min.setValue(ymin)
        self.axisY.max.setValue(ymax)
        if self.fig.dim == 3:
            self.axisZ.label.setText(self.fig.ax.get_zlabel())
            zcolor = self.fig.ax.zaxis.get_label().get_color()
            self.axisZ.label.setColor(QtGui.QColor(zcolor))
            zmin, zmax = self.fig.ax.get_zlim()
            self.axisZ.min.setValue(zmin)
            self.axisZ.max.setValue(zmax)

    def update(self, key, value):
        """Update plot
        Input:
            key: plot parameter key to update
            value: new value for key
        """
        f = {"xlabel": self.fig.ax.set_xlabel,
             "xlabelcolor": self.fig.ax.xaxis.get_label().set_color,
             "xlabelfont": self.fig.ax.xaxis.get_label().set_fontproperties,
             "ylabel": self.fig.ax.set_ylabel,
             "ylabelcolor": self.fig.ax.yaxis.get_label().set_color,
             "ylabelfont": self.fig.ax.yaxis.get_label().set_fontproperties,
             "title": self.fig.ax.set_title,
             "titlecolor": self.fig.ax.title.set_color,
             "titlefont": self.fig.ax.title.set_fontproperties,
             "xscale": self.fig.ax.set_xscale,
             "yscale": self.fig.ax.set_yscale,
             "grid": self.fig.ax.grid}

        if self.fig.dim == 3:
            f["zlabel"] = self.fig.ax.set_zlabel
            f["zlabelcolor"] = self.fig.ax.zaxis.get_label().set_color
            f["zlabelfont"] = self.fig.ax.zaxis.get_label().set_fontproperties

        if key in ("xscale", "yscale"):
            if value:
                value = "log"
            else:
                value = "linear"
        if key == "grid":
            self.fig.ax._gridOn = value
        if key in ("titlecolor", "xlabelcolor", "ylabelcolor"):
            value = str(value)
        if key in ("titlefont", "xlabelfont", "ylabelfont"):
            value = convertFont(value)

        if key in ("xmin", "xmax"):
            xmin = self.axisX.min.value
            xmax = self.axisX.max.value
            self.fig.ax.set_xlim(xmin, xmax)
        elif key in ("ymin", "ymax"):
            ymin = self.axisY.min.value
            ymax = self.axisY.max.value
            self.fig.ax.set_ylim(ymin, ymax)
        elif key in ("zmin", "zmax"):
            ymin = self.axisZ.min.value
            ymax = self.axisZ.max.value
            self.fig.ax.set_zlim(ymin, ymax)
        else:
            f[key](value)
        self.fig.draw()


def convertFont(qfont):
    """Convert qt QFont class properties to FontProperties to use in
    matplotlib

    Parameters
    ----------
    qfont : QFont
        QFont with properties to extract

    Returns
    -------
    font : FontProperties
        FontProperties instance to use in any matplotlib text instance
    """
    family = str(qfont.family())

    # Matplotlib use 0-1000 scale, qt only 0-100 scale
    weight = 10*qfont.weight()

    if qfont.style() == 0:
        style = "normal"
    elif qfont.style() == 1:
        style = "italic"
    elif qfont.style() == 2:
        style = "oblique"
    else:
        style = None
    print(family, style, qfont.stretch(), weight, qfont.pointSize())
    font = FontProperties(family, style, None, qfont.stretch(),
                          weight, qfont.pointSize())

    return font


class AxisWidget(QtWidgets.QGroupBox):
    """Dialog to configure axes plot properties"""
    def __init__(self, name, parent=None):
        title = name+" "+QtWidgets.QApplication.translate("pychemqt", "Axis")
        super(AxisWidget, self).__init__(title, parent)
        lyt = QtWidgets.QGridLayout(self)
        lyt.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "Label")), 1, 1)
        self.label = InputFont()
        lyt.addWidget(self.label, 1, 2)
        self.scale = QtWidgets.QCheckBox(
            QtWidgets.QApplication.translate("pychemqt", "Logarithmic scale"))
        lyt.addWidget(self.scale, 2, 1, 1, 2)
        lyt.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "from")), 3, 1)
        self.min = Entrada_con_unidades(float, min=float("-inf"))
        lyt.addWidget(self.min, 3, 2)
        lyt.addWidget(QtWidgets.QLabel(
            QtWidgets.QApplication.translate("pychemqt", "to")), 4, 1)
        self.max = Entrada_con_unidades(float, min=float("-inf"))
        lyt.addWidget(self.max, 4, 2)


def calcIsoline(f, config, var, fix, vvar, vfix, ini, step, end, total, bar):
    """Procedure to calculate isoline. In isotherm and isobar add to calculate
    point the saturated states in two-phases region"""
    fluidos = []
    # fase = None
    rhoo = 0
    To = 0
    for Ti in vvar:
        kwargs = {var: Ti, fix: vfix, "rho0": rhoo, "T0": To}
        print(kwargs)
        fluido = calcPoint(f, config, **kwargs)
        if fluido and fluido.status and (fluido.rho != rhoo or fluido.T != To):
            if var not in ("T", "P") or fix not in ("T", "P"):
                rhoo = fluido.rho
                To = fluido.T

            fluidos.append(fluido)
            # FIXME: Fix added point order
            # if var in ("T", "P") and fix in ("T", "P"):
                # if fase is None:
                    # fase = fluido.x
                # if fase != fluido.x and fase <= 0:
                    # if fluido.P < f.Pc and fluido.T < f.Tc:
                        # fluido_x0 = calcPoint(f, config, **{fix: vfix, "x": 0.})
                        # fluidos.insert(-1, fluido_x0)
                # elif fase != fluido.x and fase >= 1:
                    # if fluido.P < f.Pc and fluido.T < f.Tc:
                        # fluido_x1 = calcPoint(f, config, **{fix: vfix, "x": 1.})
                        # fluidos.insert(-1, fluido_x1)
                # if fase != fluido.x and fluido.x >= 1:
                    # if fluido.P < f.Pc and fluido.T < f.Tc:
                        # fluido_x1 = calcPoint(f, config, **{fix: vfix, "x": 1.})
                        # fluidos.insert(-1, fluido_x1)
# #                        rhoo = fluido_x1.rho
# #                        To = fluido_x1.T
                # elif fase != fluido.x and fluido.x <= 0:
                    # if fluido.P < f.Pc and fluido.T < f.Tc:
                        # fluido_x0 = calcPoint(f, config, **{fix: vfix, "x": 0.})
                        # fluidos.insert(-1, fluido_x0)
# #                        rhoo = fluido_x0.rho
# #                        To = fluido_x0.T
                # fase = fluido.x

        bar.setValue(ini+end*step/total+end/total*len(fluidos)/len(vvar))
        QtWidgets.QApplication.processEvents()
    return fluidos


def get_points(Preferences):
    """Get point number to plot lines from Preferences"""
    definition = Preferences.getint("MEOS", "definition")
    if definition == 1:
        points = 10
    elif definition == 2:
        points = 25
    elif definition == 3:
        points = 50
    elif definition == 4:
        points = 100
    else:
        points = 5
    return points


def getLineFormat(Preferences, name):
    """get matplotlib line format from preferences
        Preferences: configparser instance with pycheqmt preferences
        name: name of isoline"""
    format = formatLine(Preferences, "MEOS", name)

    # Anotation
    if name != "saturation":
        format["annotate"] = Preferences.getboolean("MEOS", name+"label")
        format["pos"] = Preferences.getint("MEOS", name+"position")
        format["unit"] = Preferences.getboolean("MEOS", name+"units")
        format["variable"] = Preferences.getboolean("MEOS", name+"variable")

    return format


def plotIsoline(data, axis, title, unidad, grafico, transform, **format):
    """Procedure to plot any isoline
    Input:
        data: section of property isoline of matrix data
        axis: array with keys of three axis, z None in 2D plot
        title: key of isoline type
        unidad: unidades subclass with isoline unit
        grafico: PlotMEoS instance to plot data
        transform: unit transform function for use configurated units in plots
        format: any matplotlib plot kwargs
    """
    x, y, z = axis
    fx, fy, fz = transform
    xscale = grafico.plot.ax.get_xscale()
    yscale = grafico.plot.ax.get_yscale()
    annotate = format.pop("annotate")
    pos = format.pop("pos")
    unit = format.pop("unit")
    variable = format.pop("variable")
    for key in sorted(data.keys()):
        xi = list(map(fx, data[key][x]))
        yi = list(map(fy, data[key][y]))
        label = "%s =%s" % (title, unidad(key).str)
        if z:
            zi = list(map(fz, data[key][z]))
            line, = grafico.plot.ax.plot(xi, yi, zi, label=label, **format)
        else:
            line, = grafico.plot.ax.plot(xi, yi, label=label, **format)

        # Add annotate for isolines
        # if annotate and not z:
        if variable and unit:
            txt = label
        elif variable:
            txt = "%s =%s" % (title, unidad(key).config())
        elif unit:
            txt = unidad(key).str
        else:
            txt = unidad(key).config()

        xmin, xmax = grafico.plot.ax.get_xlim()
        ymin, ymax = grafico.plot.ax.get_ylim()

        i = int(len(xi)*pos/100)
        if i >= len(xi):
            i = len(yi)-1
        print(xi)

        if pos > 50:
            j = i-10
        else:
            j = i+10
        if xscale == "log":
            f_x = (log(xi[i])-log(xi[j]))/(log(xmax)-log(xmin))
        else:
            f_x = (xi[i]-xi[j])/(xmax-xmin)
        if yscale == "log":
            f_y = (log(yi[i])-log(yi[j]))/(log(ymax)-log(ymin))
        else:
            f_y = (yi[i]-yi[j])/(ymax-ymin)

        rot = atan(f_y/f_x)*360/2/pi

        kw = {}
        kw["ha"] = "center"
        kw["va"] = "center_baseline"
        kw["rotation_mode"] = "anchor"
        kw["rotation"] = rot
        kw["size"] = "small"
        text = grafico.plot.ax.text(xi[i], yi[i], txt, **kw)

        line.text = text
        line.text.pos = pos
        if not annotate:
            text.set_visible(False)


def plot2D3D(grafico, data, Preferences, x, y, z=None):
    """Plot procedure
    Parameters:
        grafico: plot
        data: data to plot
        Preferences: ConfigParser instance from mainwindow preferencesChanged
        x: Key for x axis
        y: Key for y axis
        z: Key for z axis Optional for 3D plot"""

    functionx = _getunitTransform(x)
    functiony = _getunitTransform(y)
    functionz = _getunitTransform(z)
    transform = (functionx, functiony, functionz)

    # Plot saturation lines
    format = getLineFormat(Preferences, "saturation")
    if x == "P" and y == "T":
        satLines = QtWidgets.QApplication.translate(
            "pychemqt", "Saturation Line"),
    else:
        satLines = [
            QtWidgets.QApplication.translate(
                "pychemqt", "Liquid Saturation Line"),
            QtWidgets.QApplication.translate(
                "pychemqt", "Vapor Saturation Line")]
    for fase, label in enumerate(satLines):
        xsat = list(map(functionx, data["saturation_%i" % fase][x]))
        ysat = list(map(functiony, data["saturation_%i" % fase][y]))
        if z:
            zsat = list(map(functionz, data["saturation_%i" % fase][z]))
            grafico.plot.ax.plot(xsat, ysat, zsat, label=label, **format)
        else:
            grafico.plot.ax.plot(xsat, ysat, label=label, **format)

    # Plot melting and sublimation lines
    if "melting" in data:
        label = QtWidgets.QApplication.translate("pychemqt", "Melting Line")
        xmel = list(map(functionx, data["melting"][x]))
        ymel = list(map(functiony, data["melting"][y]))
        if z:
            zmel = list(map(functionz, data["melting"][z]))
            grafico.plot.ax.plot(xmel, ymel, zmel, label=label, **format)
        else:
            grafico.plot.ax.plot(xmel, ymel, label=label, **format)
    if "sublimation" in data:
        xsub = list(map(functionx, data["sublimation"][x]))
        ysub = list(map(functiony, data["sublimation"][y]))
        label = QtWidgets.QApplication.translate(
            "pychemqt", "Sublimation Line")
        if z:
            zmel = list(map(functionz, data["melting"][z]))
            grafico.plot.ax.plot(xmel, ymel, zmel, label=label, **format)
        else:
            grafico.plot.ax.plot(xsub, ysub, label=label, **format)

    # Plot quality isolines
    if x not in ["P", "T"] or y not in ["P", "T"] or z:
        format = getLineFormat(Preferences, "Isoquality")
        plotIsoline(data["x"], (x, y, z), "x", unidades.Dimensionless, grafico,
                    transform, **format)

    # Plot isotherm lines
    if x != "T" and y != "T" or z:
        format = getLineFormat(Preferences, "Isotherm")
        plotIsoline(data["T"], (x, y, z), "T", unidades.Temperature, grafico,
                    transform, **format)

    # Plot isobar lines
    if x != "P" and y != "P" or z:
        format = getLineFormat(Preferences, "Isobar")
        plotIsoline(data["P"], (x, y, z), "P", unidades.Pressure, grafico,
                    transform, **format)

    # Plot isochor lines
    if x not in ["rho", "v"] and y not in ["rho", "v"] or z:
        format = getLineFormat(Preferences, "Isochor")
        plotIsoline(data["v"], (x, y, z), "v", unidades.SpecificVolume,
                    grafico, transform, **format)
        # Plot isodensity lines
        if "rho" in data:
            plotIsoline(data["rho"], (x, y, z), "rho", unidades.Density,
                        grafico, transform, **format)

    # Plot isoenthalpic lines
    if x != "h" and y != "h" or z:
        format = getLineFormat(Preferences, "Isoenthalpic")
        plotIsoline(data["h"], (x, y, z), "h", unidades.Enthalpy, grafico,
                    transform, **format)

    # Plot isoentropic lines
    if x != "s" and y != "s" or z:
        format = getLineFormat(Preferences, "Isoentropic")
        plotIsoline(data["s"], (x, y, z), "s", unidades.SpecificHeat, grafico,
                    transform, **format)


def _getunitTransform(eje):
    """Return the axis unit transform function to map data to configurated unit
        Parameters:
            seq: list with axis property keys
    """
    if not eje:
        return None
    elif eje == "T":
        index = config.getMainWindowConfig().getint("Units", "Temperature")
        func = [float, unidades.K2C, unidades.K2R, unidades.K2F, unidades.K2Re]
        return func[index]
    else:
        unit = meos.units[meos.keys.index(eje)]
        factor = unit(1.).config()
        return lambda val: val*factor if val is not None else nan


def calcPoint(fluid, config, **kwargs):
    """Procedure to calculate point state and check state in P-T range of eq"""
    method = getMethod()
    if method == "MEOS":
        if isinstance(config, dict):
            option = config
        else:
            option = {}
            option["eq"] = config.getint("MEoS", "eq")
            option["visco"] = config.getint("MEoS", "visco")
            option["thermal"] = config.getint("MEoS", "thermal")
        kwargs.update(option)
        Tmin = fluid.eq[option["eq"]]["Tmin"]
        Tmax = fluid.eq[option["eq"]]["Tmax"]
        Pmin = fluid(T=fluid.eq[option["eq"]]["Tmin"], x=0).P
        Pmax = fluid.eq[option["eq"]]["Pmax"]*1000
    elif method == "COOLPROP":
        Tmin = fluid.eq["Tmin"]
        Tmax = fluid.eq["Tmax"]
        Pmin = fluid.eq["Pmin"]
        Pmax = fluid.eq["Pmax"]
    elif method == "REFPROP":
        pass

    if "T" in kwargs:
        if kwargs["T"] < Tmin or kwargs["T"] > Tmax:
            return None
    if "P" in kwargs:
        if kwargs["P"] < Pmin-1 or kwargs["P"] > Pmax+1:
            return None
    fluido = fluid._new(**kwargs)

    if fluido.status not in [1, 3]:
        return None

    if method == "MEOS":
        if fluido._melting and fluido._melting["Tmin"] <= fluido.T\
                <= fluido._melting["Tmax"]:
            Pmel = fluido._Melting_Pressure(fluido.T)
            Pmax = min(Pmax, Pmel)

    if fluido.P < Pmin-1 or fluido.P > Pmax+1 or fluido.T < Tmin\
            or fluido.T > Tmax:
        return None
    return fluido


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)

    conf = config.getMainWindowConfig()

    # SteamTables = Ui_ChooseFluid()
    SteamTables = Dialog_InfoFluid(mEoS.He)
    # SteamTables = AddPoint(conf)
    # SteamTables=AddLine(None)
    # SteamTables=transportDialog(mEoS.__all__[2])
    # SteamTables = Dialog(conf)
    # SteamTables = Plot3D()

    SteamTables.show()
    sys.exit(app.exec_())
