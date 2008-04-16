""" spyke.gui.main

Main spyke interface window.
"""

import wx
import wx.html
import cPickle
import os
from wx.lib import buttons

class Nothing(object):
    def __getattribute__(self, attr):
        return lambda *args, **kwargs: None

class SpykeFrame(wx.Frame):
    def __init__(self, parent):
        self.title = "spyke"
        wx.Frame.__init__(self, parent, -1, self.title,
                size=(400, 300))
        self.sketch = Nothing() # what the hell is a sketch?
        self.filename = ""
        self.initStatusBar()
        self.createMenuBar()
        self.createToolBar()

    def initStatusBar(self):
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetFieldsCount(3)
        self.statusbar.SetStatusWidths([-1, -2, -3])

    def OnSketchMotion(self, event):
        self.statusbar.SetStatusText("Pos: %s" %
                str(event.GetPositionTuple()), 0)
        self.statusbar.SetStatusText("Current Pts: %s" %
                len(self.sketch.curLine), 1)
        self.statusbar.SetStatusText("Line Count: %s" %
                len(self.sketch.lines), 2)
        event.Skip()

    def menuData(self):
        return [("&File", (
                    ("&New", "Create new collection", self.OnNew),
                    ("&Open", "Open collection", self.OnOpen),
                    ("&Save", "Save collection", self.OnSave),
                    ("", "", ""),
                    ("About...", "Show about window", self.OnAbout),
                    ("&Quit", "Quit", self.OnCloseWindow)))]

    def createMenuBar(self):
        menuBar = wx.MenuBar()
        for eachMenuData in self.menuData():
            menuLabel = eachMenuData[0]
            menuItems = eachMenuData[1]
            menuBar.Append(self.createMenu(menuItems), menuLabel)
        self.SetMenuBar(menuBar)

    def createMenu(self, menuData):
        menu = wx.Menu()
        for eachItem in menuData:
            if len(eachItem) == 2:
                label = eachItem[0]
                subMenu = self.createMenu(eachItem[1])
                menu.AppendMenu(wx.NewId(), label, subMenu)
            else:
                self.createMenuItem(menu, *eachItem)
        return menu

    def createMenuItem(self, menu, label, status, handler, kind=wx.ITEM_NORMAL):
        if not label:
            menu.AppendSeparator()
            return
        menuItem = menu.Append(-1, label, status, kind)
        self.Bind(wx.EVT_MENU, handler, menuItem)

    def createToolBar(self):
        toolbar = self.CreateToolBar()
        for each in self.toolbarData():
            self.createSimpleTool(toolbar, *each)
        toolbar.Realize()

    def createSimpleTool(self, toolbar, label, filename, help, handler):
        if not label:
            toolbar.AddSeparator()
            return
        bmp = wx.Image(filename, wx.BITMAP_TYPE_BMP).ConvertToBitmap()
        tool = toolbar.AddSimpleTool(-1, bmp, label, help)
        self.Bind(wx.EVT_MENU, handler, tool)

    def toolbarData(self):
        return (("New", "res/new.bmp", "Create new collection", self.OnNew),
                ("", "", "", ""),
                ("Open", "res/open.bmp", "Open collection", self.OnOpen),
                ("Save", "res/save.bmp", "Save collection", self.OnSave))

    def createColorTool(self, toolbar, color):
        bmp = self.MakeBitmap(color)
        tool = toolbar.AddRadioTool(-1, bmp, shortHelp=color)
        self.Bind(wx.EVT_MENU, self.OnColor, tool)

    def MakeBitmap(self, color):
        bmp = wx.EmptyBitmap(16, 15)
        dc = wx.MemoryDC()
        dc.SelectObject(bmp)
        dc.SetBackground(wx.Brush(color))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        return bmp

    def toolbarColorData(self):
        return ("Black", "Red", "Green", "Blue")

    def OnNew(self, event): pass

    def OnColor(self, event):
        menubar = self.GetMenuBar()
        itemId = event.GetId()
        item = menubar.FindItemById(itemId)
        if not item:
            toolbar = self.GetToolBar()
            item = toolbar.FindById(itemId)
            color = item.GetShortHelp()
        else:
            color = item.GetLabel()
        self.sketch.SetColor(color)

    def OnCloseWindow(self, event):
        self.Destroy()

    def SaveFile(self):
        if self.filename:
            data = self.sketch.GetLinesData()
            f = open(self.filename, 'w')
            cPickle.dump(data, f)
            f.close()

    def ReadFile(self):
        if self.filename:
            try:
                f = open(self.filename, 'r')
                data = cPickle.load(f)
                f.close()
            except cPickle.UnpicklingError:
                wx.MessageBox("%s is not a sketch file." % self.filename,
                              "oops!", style=wx.OK|wx.ICON_EXCLAMATION)

    wildcard = "Collection files (*.pickle.gz)|*.pickle.gz|All files (*.*)|*.*"

    def OnOpen(self, event):
        dlg = wx.FileDialog(self, "Open collection file...", os.getcwd(),
                            style=wx.OPEN, wildcard=self.wildcard)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetPath()
            self.ReadFile()
            self.SetTitle(self.title + ' -- ' + self.filename)
        dlg.Destroy()

    def OnSave(self, event):
        if not self.filename:
            self.OnSaveAs(event)
        else:
            self.SaveFile()

    def OnSaveAs(self, event):
        dlg = wx.FileDialog(self, "Save collection as...", os.getcwd(),
                            style=wx.SAVE | wx.OVERWRITE_PROMPT,
                            wildcard = self.wildcard)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            if not os.path.splitext(filename)[1]:
                filename = filename + '.pickle.gz'
            self.filename = filename
            self.SaveFile()
            self.SetTitle(self.title + ' -- ' + self.filename)
        dlg.Destroy()

    def OnOtherColor(self, event):
        dlg = wx.ColourDialog(frame)
        dlg.GetColourData().SetChooseFull(True)
        if dlg.ShowModal() == wx.ID_OK:
            self.sketch.SetColor(dlg.GetColourData().GetColour())
        dlg.Destroy()

    def OnAbout(self, event):
        dlg = SpykeAbout(self)
        dlg.ShowModal()
        dlg.Destroy()


class SpykeAbout(wx.Dialog):
    text = '''
<html>
<body bgcolor="#ACAA60">
<center><table bgcolor="#455481" width="100%" cellspacing="0"
cellpadding="0" border="1">
<tr>
    <td align="center"><h1>Spyke</h1></td>
</tr>
</table>
</center>
<p><b>spyke</b> is a tool for neuronal spike sorting.
</p>

<p>Copyright &copy; 2008, Reza Lotun, Martin Spacek</p>
</body>
</html>
'''

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, 'About spyke',
                          size=(300, 300) )

        html = wx.html.HtmlWindow(self)
        html.SetPage(self.text)
        button = wx.Button(self, wx.ID_OK, "OK")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(html, 1, wx.EXPAND|wx.ALL, 5)
        sizer.Add(button, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        self.SetSizer(sizer)
        self.Layout()



class SpykeApp(wx.App):

    def OnInit(self, splash=False):
        if splash:
            bmp = wx.Image("res/splash.png").ConvertToBitmap()
            wx.SplashScreen(bmp, wx.SPLASH_CENTRE_ON_SCREEN | wx.SPLASH_TIMEOUT,
                1000, None, -1)
            wx.Yield()

        frame = SpykeFrame(None)
        frame.Show(True)
        self.SetTopWindow(frame)
        return True

if __name__ == '__main__':
    app = SpykeApp(False)
    app.MainLoop()
