import wx
import wx.aui as aui
import functools
import json
import math

json.encoder.FLOAT_REPR = lambda x: format(x, '.2f')

TITLE = 'Star Edit'
DEFAULT_NAME = '(Untitled)'
DEFAULT_BOUNDS = (-240, -160, 240, 160) # LBRT
DEFAULT_SCALE = 0.5

RADIUS_ASTEROID = 32
RADIUS_BUMPER = 64
RADIUS_ITEM = 12
RADIUS_PLANET = 64
RADIUS_ROCKET = 20
RADIUS_STAR = 12

CODE_ASTEROID = 'A'
CODE_BUMPER = 'B'
CODE_ITEM = 'I'
CODE_PLANET = 'P'
CODE_ROCKET = 'R'
CODE_STAR = 'S'

PATH_CIRCULAR = 1
PATH_LINEAR = 2

# Utility Functions
def menu_item(window, menu, label, func, icon=None):
    item = wx.MenuItem(menu, -1, label)
    icon = icon or icons.blank
    item.SetBitmap(icon.GetBitmap())
    if func:
        window.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.AppendItem(item)
    return item
    
def tool_item(window, toolbar, label, func, icon):
    item = toolbar.AddSimpleTool(-1, icon.GetBitmap(), label)
    if func:
        window.Bind(wx.EVT_TOOL, func, id=item.GetId())
    return item
    
def set_icon(window):
    bundle = wx.IconBundle()
    bundle.AddIcon(wx.IconFromBitmap(icons.icon16.GetBitmap()))
    bundle.AddIcon(wx.IconFromBitmap(icons.icon32.GetBitmap()))
    window.SetIcons(bundle)
    
def change_font(widget, size=None, bold=None, italic=None, underline=None):
    font = widget.GetFont()
    if size is not None:
        font.SetPointSize(size)
    if bold is not None:
        font.SetWeight(wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL)
    if italic is not None:
        font.SetStyle(wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL)
    if underline is not None:
        font.SetUnderlined(underline)
    widget.SetFont(font)
    
def set_choice(choice, value):
    count = choice.GetCount()
    for index in range(count):
        if choice.GetClientData(index) == value:
            choice.Select(index)
            break
    else:
        choice.Select(wx.NOT_FOUND)
        
def get_choice(choice):
    index = choice.GetSelection()
    if index < 0:
        return None
    return choice.GetClientData(index)
    
def copy_path(src, dest):
    if src.path:
        dest.path = src.path.copy()
    return dest
    
# Model Classes
class Project(object):
    def __init__(self):
        self.levels = [Level()]
    @property
    def key(self):
        return [level.key for level in self.levels]
    @staticmethod
    def from_key(key):
        project = Project()
        project.levels = [Level.from_key(subkey) for subkey in key]
        return project
    def save(self, path):
        data = json.dumps(self.key)#, sort_keys=True, indent=4)
        with open(path, 'w') as file:
            file.write(data)
    @staticmethod
    def load(path):
        with open(path, 'r') as file:
            data = file.read()
        key = json.loads(data)
        return Project.from_key(key)
        
class Level(object):
    def __init__(self):
        self.name = DEFAULT_NAME
        self.bounds = DEFAULT_BOUNDS
        self.entities = [Rocket(0, 0)]
    def entities_of_type(self, cls):
        return [entity for entity in self.entities if isinstance(entity, cls)]
    def keys_of_type(self, cls):
        result = []
        entities = self.entities_of_type(cls)
        for entity in entities:
            key = entity.key
            if entity.path:
                key['path'] = entity.path.key
            result.append(key)
        return result
    def copy(self):
        level = Level()
        level.name = self.name
        level.bounds = self.bounds
        level.entities = [entity.copy() for entity in self.entities]
        return level
    def restore(self, other):
        self.name = other.name
        self.bounds = other.bounds
        self.entities = [entity.copy() for entity in other.entities]
    @property
    def key(self):
        entities = {
            'asteroids': self.keys_of_type(Asteroid),
            'bumpers': self.keys_of_type(Bumper),
            'items': self.keys_of_type(Item),
            'planets': self.keys_of_type(Planet),
            'rockets': self.keys_of_type(Rocket),
            'stars': self.keys_of_type(Star),
        }
        result = {
            'name': self.name,
            'bounds': self.bounds,
            'entities': entities,
        }
        return result
    @staticmethod
    def from_key(key):
        level = Level()
        level.name = key.get('name', DEFAULT_NAME)
        level.bounds = tuple(key.get('bounds', DEFAULT_BOUNDS))
        entities_data = key.get('entities', {})
        mapping = [
            ('asteroids', Asteroid),
            ('bumpers', Bumper),
            ('items', Item),
            ('planets', Planet),
            ('rockets', Rocket),
            ('stars', Star),
        ]
        path_mapping = {
            PATH_CIRCULAR: CircularPath,
            PATH_LINEAR: LinearPath,
        }
        entities = []
        for name, cls in mapping:
            keys = entities_data.get(name, [])
            for key in keys:
                entity = cls.from_key(key)
                path_key = key.get('path', None)
                if path_key:
                    path_cls = path_mapping[path_key['type']]
                    path = path_cls.from_key(path_key)
                    entity.path = path
                entities.append(entity)
        level.entities = entities
        return level
        
class Entity(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.path = None
    def contains(self, x, y):
        radius = self.radius
        dx = abs(x - self.x)
        dy = abs(y - self.y)
        if dx > radius or dy > radius:
            return False
        distance = (dx * dx + dy * dy) ** 0.5
        return distance <= radius
    def inside(self, l, b, r, t):
        x, y = self.x, self.y
        radius = self.radius
        if x < l + radius:
            return False
        if y < b + radius:
            return False
        if x > r - radius:
            return False
        if y > t - radius:
            return False
        return True
        
class CircularPath(object):
    def __init__(self, radius, angle, period, clockwise):
        self.radius = radius
        self.angle = angle
        self.period = period
        self.clockwise = clockwise
    @property
    def key(self):
        result = {
            'type': PATH_CIRCULAR,
            'radius': self.radius,
            'angle': self.angle,
            'period': self.period,
            'clockwise': self.clockwise,
        }
        return result
    @staticmethod
    def from_key(key):
        radius = key['radius']
        angle = key['angle']
        period = key['period']
        clockwise = key['clockwise']
        return CircularPath(radius, angle, period, clockwise)
    def copy(self):
        return CircularPath(self.radius, self.angle, self.period, self.clockwise)
        
class LinearPath(object):
    def __init__(self, dx, dy, period):
        self.dx = dx
        self.dy = dy
        self.period = period
    @property
    def key(self):
        result = {
            'type': PATH_LINEAR,
            'dx': self.dx,
            'dy': self.dy,
            'period': self.period,
        }
        return result
    @staticmethod
    def from_key(key):
        dx = key['dx']
        dy = key['dy']
        period = key['period']
        return LinearPath(dx, dy, period)
    def copy(self):
        return LinearPath(self.dx, self.dy, self.period)
        
class Rocket(Entity):
    code = CODE_ROCKET
    radius = RADIUS_ROCKET
    stroke = (127, 0, 0)
    fill = (255, 127, 127)
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        return Rocket(x, y)
    def copy(self):
        return copy_path(self, Rocket(self.x, self.y))
        
class Planet(Entity):
    code = CODE_PLANET
    stroke = (64, 64, 64)
    fill = (128, 128, 128)
    def __init__(self, x, y, scale, sprite):
        super(Planet, self).__init__(x, y)
        self.scale = scale
        self.sprite = sprite
    @property
    def radius(self):
        return RADIUS_PLANET * self.scale
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
            'scale': self.scale,
            'sprite': self.sprite,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        scale = key.get('scale', DEFAULT_SCALE)
        sprite = key.get('sprite', 0)
        return Planet(x, y, scale, sprite)
    def copy(self):
        return copy_path(self, Planet(self.x, self.y, self.scale, self.sprite))
        
class Bumper(Entity):
    code = CODE_BUMPER
    stroke = (0, 40, 127)
    fill = (50, 115, 255)
    def __init__(self, x, y, scale):
        super(Bumper, self).__init__(x, y)
        self.scale = scale
    @property
    def radius(self):
        return RADIUS_BUMPER * self.scale
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
            'scale': self.scale,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        scale = key.get('scale', DEFAULT_SCALE)
        return Bumper(x, y, scale)
    def copy(self):
        return copy_path(self, Bumper(self.x, self.y, self.scale))
        
class Asteroid(Entity):
    code = CODE_ASTEROID
    stroke = (63, 44, 31)
    fill = (191, 133, 95)
    def __init__(self, x, y, scale):
        super(Asteroid, self).__init__(x, y)
        self.scale = scale
    @property
    def radius(self):
        return RADIUS_ASTEROID * self.scale
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
            'scale': self.scale,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        scale = key.get('scale', DEFAULT_SCALE)
        return Asteroid(x, y, scale)
    def copy(self):
        return copy_path(self, Asteroid(self.x, self.y, self.scale))
        
class Item(Entity):
    code = CODE_ITEM
    radius = RADIUS_ITEM
    stroke = (0, 127, 14)
    fill = (127, 255, 142)
    def __init__(self, x, y, type):
        super(Item, self).__init__(x, y)
        self.type = type
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
            'type': self.type,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        type = key.get('type', 0)
        return Item(x, y, type)
    def copy(self):
        return copy_path(self, Item(self.x, self.y, self.type))
        
class Star(Entity):
    code = CODE_STAR
    radius = RADIUS_STAR
    stroke = (255, 127, 0)
    fill = (255, 233, 127)
    @property
    def key(self):
        result = {
            'x': self.x,
            'y': self.y,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key.get('x', 0)
        y = key.get('y', 0)
        return Star(x, y)
    def copy(self):
        return copy_path(self, Star(self.x, self.y))
        
# View Classes
EVT_ENTITY_DCLICK = wx.PyEventBinder(wx.NewEventType())
EVT_LEVEL_ADD = wx.PyEventBinder(wx.NewEventType())
EVT_LEVEL_DELETE = wx.PyEventBinder(wx.NewEventType())
EVT_LEVEL_MOVE_UP = wx.PyEventBinder(wx.NewEventType())
EVT_LEVEL_MOVE_DOWN = wx.PyEventBinder(wx.NewEventType())
EVT_LEVEL_PROPERTES = wx.PyEventBinder(wx.NewEventType())
EVT_CONTROL_CHANGED = wx.PyEventBinder(wx.NewEventType())

class Event(wx.PyEvent):
    def __init__(self, event_object, type):
        super(Event, self).__init__()
        self.SetEventType(type.typeId)
        self.SetEventObject(event_object)
        
class Frame(wx.Frame):
    def __init__(self):
        super(Frame, self).__init__(None, -1, TITLE)
        self.project = None
        self._path = None
        self._unsaved = False
        self.create_manager()
        self.create_menu()
        self.create_statusbar()
        self.new()
        self.set_default_size()
        self.Center()
        set_icon(self)
        self.Bind(wx.EVT_CLOSE, self.on_close)
    @property
    def control(self):
        index = self.notebook.GetSelection()
        window = self.notebook.GetPage(index)
        return window.control
    def set_default_size(self):
        w = wx.SystemSettings_GetMetric(wx.SYS_SCREEN_X)
        h = wx.SystemSettings_GetMetric(wx.SYS_SCREEN_Y)
        wr, hr = (5, 4)
        pad = min(w / 8, h / 8)
        n = min((w - pad) / wr, (h - pad) / hr)
        size = (n * wr, n * hr)
        self.SetSize(size)
    def create_manager(self):
        self.manager = aui.AuiManager(self)
        # Notebook
        self.notebook = self.create_notebook(self)
        info = aui.AuiPaneInfo()
        info.Name('notebook')
        info.CentrePane()
        info.PaneBorder(False)
        self.manager.AddPane(self.notebook, info)
        # Level List
        self.level_view = self.create_level_view(self)
        info = aui.AuiPaneInfo()
        info.Name('level_view')
        info.Left()
        info.Caption('Levels')
        size = (32 + 48 + 128 + 32, -1)
        info.MinSize(size)
        info.BestSize(size)
        info.FloatingSize(size)
        self.manager.AddPane(self.level_view, info)
        # Toolbar
        toolbar = self.create_toolbar()
        info = aui.AuiPaneInfo()
        info.Name('toolbar')
        info.ToolbarPane()
        info.LeftDockable(False)
        info.RightDockable(False)
        info.PaneBorder(False)
        info.Top()
        self.manager.AddPane(toolbar, info)
        self.manager.Update()
    def create_notebook(self, parent):
        style = wx.BORDER_NONE
        style |= aui.AUI_NB_TAB_MOVE
        style |= aui.AUI_NB_CLOSE_BUTTON
        style |= aui.AUI_NB_SCROLL_BUTTONS
        style |= aui.AUI_NB_WINDOWLIST_BUTTON
        notebook = aui.AuiNotebook(parent, -1, style=style)
        notebook.SetUniformBitmapSize((21, 21))
        notebook.Bind(aui.EVT_AUINOTEBOOK_PAGE_CLOSED, self.on_page_closed)
        return notebook
    def create_level_view(self, parent):
        level_view = LevelView(parent)
        level_list = level_view.level_list
        #level_list.Bind(wx.EVT_LEFT_DCLICK, self.on_level_dclick)
        
        level_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_level_selected)
        level_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_level_activated)
        
        level_view.Bind(EVT_LEVEL_ADD, self.on_level_add)
        level_view.Bind(EVT_LEVEL_DELETE, self.on_level_delete)
        level_view.Bind(EVT_LEVEL_MOVE_UP, self.on_level_move_up)
        level_view.Bind(EVT_LEVEL_MOVE_DOWN, self.on_level_move_down)
        level_view.Bind(EVT_LEVEL_PROPERTES, self.on_level_properties)
        return level_view
    def create_menu(self):
        menubar = wx.MenuBar()
        # File
        menu = wx.Menu()
        menu_item(self, menu, 'New\tCtrl+N', self.on_new, icons.page)
        menu_item(self, menu, 'Open...\tCtrl+O', self.on_open, icons.folder_page)
        menu.AppendSeparator()
        menu_item(self, menu, 'Save\tCtrl+S', self.on_save, icons.disk)
        menu_item(self, menu, 'Save As...\tCtrl+Shift+S', self.on_save_as)
        menu.AppendSeparator()
        menu_item(self, menu, 'Exit\tAlt+F4', self.on_exit, icons.door_out)
        menubar.Append(menu, '&File')
        # Edit
        menu = wx.Menu()
        menu_item(self, menu, 'Undo\tCtrl+Z', self.on_undo, icons.arrow_undo)
        menu_item(self, menu, 'Redo\tCtrl+Y', self.on_redo, icons.arrow_redo)
        menu.AppendSeparator()
        menu_item(self, menu, 'Cut\tCtrl+X', self.on_cut, icons.cut)
        menu_item(self, menu, 'Copy\tCtrl+C', self.on_copy, icons.page_copy)
        menu_item(self, menu, 'Paste\tCtrl+V', self.on_paste, icons.page_paste)
        menu_item(self, menu, 'Duplicate\tCtrl+D', self.on_duplicate)
        menu.AppendSeparator()
        menu_item(self, menu, 'Delete\tDel', self.on_delete, icons.page_delete)
        menu_item(self, menu, 'Select All\tCtrl+A', self.on_select_all)
        menubar.Append(menu, '&Edit')
        # View
        menu = wx.Menu()
        menu_item(self, menu, 'Next Tab\tCtrl+Tab', self.on_next_tab)
        menu_item(self, menu, 'Previous Tab\tCtrl+Shift+Tab', self.on_previous_tab)
        menu.AppendSeparator()
        menu_item(self, menu, 'Show Grid', self.on_show_grid)
        menu_item(self, menu, 'Snap to Grid', self.on_snap_to_grid)
        menu.AppendSeparator()
        menu_item(self, menu, 'Show Levels', self.on_show_levels)
        menu.AppendSeparator()
        for zoom in range(1, 5):
            func = functools.partial(self.on_zoom, zoom=zoom)
            menu_item(self, menu, '%d00%%\t%d' % (zoom, zoom), func)
        menubar.Append(menu, '&View')
        # Objects
        menu = wx.Menu()
        menu_item(self, menu, 'Rocket\tR', self.on_rocket, icons.icon_rocket)
        menu_item(self, menu, 'Star\tS', self.on_star, icons.icon_star)
        menu_item(self, menu, 'Planet\tP', self.on_planet, icons.icon_planet)
        menu_item(self, menu, 'Bumper\tB', self.on_bumper, icons.icon_bumper)
        menu_item(self, menu, 'Asteroid\tA', self.on_asteroid, icons.icon_asteroid)
        menu_item(self, menu, 'Item\tI', self.on_item, icons.icon_item)
        menubar.Append(menu, '&Objects')
        # Tools
        menu = wx.Menu()
        func = functools.partial(self.on_mirror, mx=-1)
        menu_item(self, menu, 'Mirror (X)', func, icons.shape_flip_horizontal)
        func = functools.partial(self.on_mirror, my=-1)
        menu_item(self, menu, 'Mirror (Y)', func, icons.shape_flip_vertical)
        func = functools.partial(self.on_mirror, mx=-1, my=-1)
        menu_item(self, menu, 'Mirror (Both)', func)
        menu_item(self, menu, 'Rotate...', self.on_rotate)
        menu.AppendSeparator()
        menu_item(self, menu, 'Linear Array...', self.on_linear_array, icons.arrow_left)
        menu_item(self, menu, 'Circular Array...', self.on_circular_array, icons.arrow_rotate_anticlockwise)
        menu.AppendSeparator()
        menu_item(self, menu, 'Linear Path...', self.on_linear_path)
        menu_item(self, menu, 'Circular Path...', self.on_circular_path)
        menubar.Append(menu, '&Tools')
        self.SetMenuBar(menubar)
    def create_toolbar(self):
        style= wx.HORIZONTAL | wx.TB_FLAT | wx.TB_NODIVIDER
        toolbar = wx.ToolBar(self, -1, style=style)
        toolbar.SetToolBitmapSize((18, 18))
        tool_item(self, toolbar, 'New', self.on_new, icons.page)
        tool_item(self, toolbar, 'Open', self.on_open, icons.folder_page)
        tool_item(self, toolbar, 'Save', self.on_save, icons.disk)
        toolbar.AddSeparator()
        tool_item(self, toolbar, 'Undo', self.on_undo, icons.arrow_undo)
        tool_item(self, toolbar, 'Redo', self.on_redo, icons.arrow_redo)
        toolbar.AddSeparator()
        tool_item(self, toolbar, 'Cut', self.on_cut, icons.cut)
        tool_item(self, toolbar, 'Copy', self.on_copy, icons.page_copy)
        tool_item(self, toolbar, 'Paste', self.on_paste, icons.page_paste)
        tool_item(self, toolbar, 'Delete', self.on_delete, icons.page_delete)
        toolbar.AddSeparator()
        tool_item(self, toolbar, 'Rocket', self.on_rocket, icons.icon_rocket)
        tool_item(self, toolbar, 'Star', self.on_star, icons.icon_star)
        tool_item(self, toolbar, 'Planet', self.on_planet, icons.icon_planet)
        tool_item(self, toolbar, 'Bumper', self.on_bumper, icons.icon_bumper)
        tool_item(self, toolbar, 'Asteroid', self.on_asteroid, icons.icon_asteroid)
        tool_item(self, toolbar, 'Item', self.on_item, icons.icon_item)
        toolbar.AddSeparator()
        func = functools.partial(self.on_mirror, mx=-1)
        tool_item(self, toolbar, 'Mirror (X)', func, icons.shape_flip_horizontal)
        func = functools.partial(self.on_mirror, my=-1)
        tool_item(self, toolbar, 'Mirror (Y)', func, icons.shape_flip_vertical)
        tool_item(self, toolbar, 'Linear Array', self.on_linear_array, icons.arrow_left)
        tool_item(self, toolbar, 'Circular Array', self.on_circular_array, icons.arrow_rotate_anticlockwise)
        toolbar.Realize()
        toolbar.Fit()
        return toolbar
    def create_statusbar(self):
        sizes = [-1]
        statusbar = self.CreateStatusBar()
        statusbar.SetFieldsCount(len(sizes))
        statusbar.SetStatusWidths(sizes)
    def toggle_view(self, view):
        info = self.manager.GetPane(view)
        info.Show(not info.IsShown())
        self.manager.Update()
    # Notebook Functions
    def close_pages(self):
        for dummy in range(self.notebook.GetPageCount()):
            self.notebook.DeletePage(0)
    def close_page(self, level):
        index = self.get_page_index(level)
        if index >= 0:
            self.notebook.DeletePage(index)
    def show_page(self, level, focus=True):
        index = self.get_page_index(level)
        if index < 0:
            self.create_page(level, focus)
        else:
            self.notebook.SetSelection(index)
            if focus:
                page = self.notebook.GetPage(index)
                page.control.SetFocus()
    def create_page(self, level, focus=True):
        window = ScrolledWindow(self.notebook)
        window.control.Bind(EVT_CONTROL_CHANGED, self.on_control_changed)
        window.control.Bind(EVT_ENTITY_DCLICK, self.on_entity_dclick)
        window.control.set_level(level)
        self.notebook.AddPage(window, level.name)
        if focus:
            index = self.notebook.GetPageIndex(window)
            self.notebook.SetSelection(index)
            window.SetFocus()
        return window
    def get_page_index(self, level):
        for index in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(index)
            if page.control.level == level:
                return index
        return -1
    def advance_page(self, forward=True):
        index = self.notebook.GetSelection()
        count = self.notebook.GetPageCount()
        if forward:
            if index == count - 1:
                index = 0
            else:
                index += 1
        else:
            if index == 0:
                index = count - 1
            else:
                index -= 1
        self.notebook.SetSelection(index)
    # Project Functions
    def set_project(self, project):
        self.project = project
        self.level_view.set_project(project)
        self.close_pages()
        for level in project.levels:
            self.show_page(level)
            break
    def new(self):
        if self.confirm_close():
            self.set_project(Project())
            self.unsaved = False
    def on_page_closed(self, event):
        pass
    def confirm_close(self):
        if self.unsaved:
            dialog = wx.MessageDialog(self, 'Save changes before closing?', 'Unsaved Changes', wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dialog.ShowModal()
            dialog.Destroy()
            if result == wx.ID_YES:
                return self.on_save(None)
            elif result == wx.ID_NO:
                return True
            else:
                return False
        else:
            return True
    def update_title(self):
        status = '* ' if self.unsaved else ''
        path = '%s - ' % self.path if self.path else ''
        title = '%s%s%s' % (status, path, TITLE)
        self.SetTitle(title)
    @property
    def unsaved(self):
        return self._unsaved
    @unsaved.setter
    def unsaved(self, unsaved):
        self._unsaved = unsaved
        self.update_title()
    @property
    def path(self):
        return self._path
    @path.setter
    def path(self, path):
        self._path = path
        self.update_title()
    def edit_metadata(self, level):
        dialog = MetadataDialog(self, level)
        if dialog.ShowModal() == wx.ID_OK:
            index = self.get_page_index(level)
            if index >= 0:
                window = self.notebook.GetPage(index)
                window.control.update_min_size()
                window.control.changed()
                self.notebook.SetPageText(index, level.name)
            self.level_view.update_level(level)
        dialog.Destroy()
    # Event Handlers
    def on_close(self, event):
        if not self.confirm_close():
            if event.CanVeto():
                event.Veto()
                return
        event.Skip()
    def on_new(self, event):
        self.new()
    def on_open(self, event):
        if self.confirm_close():
            dialog = wx.FileDialog(self, 'Open', wildcard='*.star', style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
            result = dialog.ShowModal()
            if result == wx.ID_OK:
                path = dialog.GetPath()
                self.path = path
                project = Project.load(path)
                self.set_project(project)
                self.unsaved = False
    def on_save(self, event):
        if self.path:
            self.project.save(self.path)
            self.unsaved = False
            return True
        else:
            return self.on_save_as(None)
    def on_save_as(self, event):
        dialog = wx.FileDialog(self, 'Save', wildcard='*.star', style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        result = dialog.ShowModal()
        if result == wx.ID_OK:
            path = dialog.GetPath()
            self.path = path
            self.project.save(path)
            self.unsaved = False
            return True
        return False
    def on_level_activated(self, event):
        level = self.level_view.level_list.get_level()
        if level:
            self.edit_metadata(level)
    def on_level_selected(self, event):
        level = self.level_view.level_list.get_level()
        if level:
            self.show_page(level)
            self.level_view.level_list.SetFocus()
    def on_level_add(self, event):
        level = Level()
        self.project.levels.append(level)
        self.show_page(level)
        self.level_view.update()
    def on_level_delete(self, event):
        level = event.level
        self.project.levels.remove(level)
        self.close_page(level)
        self.level_view.update()
    def on_level_move_up(self, event):
        level = event.level
        levels = self.project.levels
        index = levels.index(level)
        if index > 0:
            other = levels[index - 1]
            levels[index] = other
            levels[index - 1] = level
            self.level_view.update()
            level_list = self.level_view.level_list
            level_list.Select(index, False)
            level_list.Select(index - 1)
            level_list.SetFocus()
    def on_level_move_down(self, event):
        level = event.level
        levels = self.project.levels
        index = levels.index(level)
        if index < len(levels) - 1:
            other = levels[index + 1]
            levels[index] = other
            levels[index + 1] = level
            self.level_view.update()
            level_list = self.level_view.level_list
            level_list.Select(index, False)
            level_list.Select(index + 1)
            level_list.SetFocus()
    def on_level_properties(self, event):
        self.edit_metadata(event.level)
    def on_exit(self, event):
        self.Close()
    def on_undo(self, event):
        self.control.undo()
    def on_redo(self, event):
        self.control.redo()
    def on_cut(self, event):
        self.control.cut()
    def on_copy(self, event):
        self.control.copy()
    def on_paste(self, event):
        self.control.paste()
    def on_duplicate(self, event):
        self.control.duplicate()
    def on_delete(self, event):
        self.control.delete()
    def on_select_all(self, event):
        self.control.select_all()
    def on_next_tab(self, event):
        self.advance_page(True)
    def on_previous_tab(self, event):
        self.advance_page(False)
    def on_show_grid(self, event):
        self.control.show_grid = not self.control.show_grid
        self.control.Refresh()
    def on_snap_to_grid(self, event):
        self.control.snap_to_grid = not self.control.snap_to_grid
        self.control.Refresh()
    def on_zoom(self, event, zoom):
        self.control.set_scale(zoom)
    def on_show_levels(self, event):
        self.toggle_view(self.level_view)
    def on_rocket(self, event):
        entity = Rocket(0, 0)
        self.control.add_entity(entity)
    def on_star(self, event):
        entity = Star(0, 0)
        self.control.add_entity(entity)
    def on_planet(self, event):
        entity = Planet(0, 0, DEFAULT_SCALE, 0)
        self.control.add_entity(entity)
    def on_bumper(self, event):
        entity = Bumper(0, 0, DEFAULT_SCALE)
        self.control.add_entity(entity)
    def on_asteroid(self, event):
        entity = Asteroid(0, 0, DEFAULT_SCALE)
        self.control.add_entity(entity)
    def on_item(self, event):
        entity = Item(0, 0, 0)
        self.control.add_entity(entity)
    def on_mirror(self, event, mx=1, my=1):
        self.control.mirror(mx, my)
    def on_rotate(self, event):
        angle = self.get_string('Enter angle (degrees):')
        try:
            angle = int(angle)
        except Exception:
            return
        self.control.rotate(angle)
    def on_linear_array(self, event):
        count = self.get_string('Enter count:')
        try:
            count = int(count)
        except Exception:
            return
        self.control.linear_array(count)
    def on_circular_array(self, event):
        count = self.get_string('Enter count:')
        try:
            count = int(count)
        except Exception:
            return
        self.control.circular_array(count)
    def on_linear_path(self, event):
        pass
    def on_circular_path(self, event):
        entities = list(self.control.selection)
        dialog = CircularPathDialog(self, entities)
        if dialog.ShowModal() == wx.ID_OK:
            self.control.changed()
        dialog.Destroy()
    def on_control_changed(self, event):
        self.unsaved = True
        level = event.GetEventObject().level
        self.level_view.update_level(level)
    def on_entity_dclick(self, event):
        entities = event.entities
        if all(isinstance(entity, Planet) for entity in entities):
            dialog = PlanetDialog(self, entities)
            if dialog.ShowModal() == wx.ID_OK:
                event.GetEventObject().changed()
            dialog.Destroy()
        elif all(isinstance(entity, (Planet, Bumper, Asteroid)) for entity in entities):
            dialog = ScaleDialog(self, entities)
            if dialog.ShowModal() == wx.ID_OK:
                event.GetEventObject().changed()
            dialog.Destroy()
        elif all(isinstance(entity, Item) for entity in entities):
            dialog = ItemDialog(self, entities)
            if dialog.ShowModal() == wx.ID_OK:
                event.GetEventObject().changed()
            dialog.Destroy()
    def get_string(self, message, default=''):
        dialog = wx.TextEntryDialog(self, message, 'Data Entry', str(default))
        if dialog.ShowModal() == wx.ID_OK:
            result = dialog.GetValue()
        else:
            result = None
        dialog.Destroy()
        return result
        
class BaseDialog(wx.Dialog):
    def __init__(self, parent, title):
        super(BaseDialog, self).__init__(parent, -1, title)
        controls = self.create_controls(self)
        line = wx.StaticLine(self, -1)
        buttons = self.create_buttons(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(controls, 1, wx.EXPAND|wx.ALL, 10)
        sizer.Add(line, 0, wx.EXPAND)
        sizer.Add(buttons, 0, wx.EXPAND|wx.ALL, 10)
        self.SetSizerAndFit(sizer)
        self.update_controls()
        self.Center()
    def create_buttons(self, parent):
        ok = wx.Button(parent, wx.ID_OK, 'OK')
        cancel = wx.Button(parent, wx.ID_CANCEL, 'Cancel')
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, self.on_ok)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(ok)
        sizer.AddSpacer(5)
        sizer.Add(cancel)
        return sizer
    def on_ok(self, event):
        event.Skip()
        self.update_model()
    def create_controls(self, parent):
        raise NotImplementedError
    def update_controls(self):
        raise NotImplementedError
    def update_model(self):
        raise NotImplementedError
        
class MetadataDialog(BaseDialog):
    def __init__(self, parent, level):
        self.level = level
        super(MetadataDialog, self).__init__(parent, 'Level Metadata')
    def create_controls(self, parent):
        grid = wx.GridBagSizer(8, 8)
        for index, name in enumerate(['name', 'left', 'bottom', 'right', 'top']):
            text = wx.StaticText(parent, -1, name.title())
            widget = wx.TextCtrl(parent, -1)
            setattr(self, name, widget)
            grid.Add(text, (index, 0), flag=wx.ALIGN_CENTER_VERTICAL)
            grid.Add(widget, (index, 1))
        return grid
    def update_controls(self):
        level = self.level
        self.name.SetValue(level.name)
        l, b, r, t = level.bounds
        self.left.SetValue(str(l))
        self.bottom.SetValue(str(b))
        self.right.SetValue(str(r))
        self.top.SetValue(str(t))
    def update_model(self):
        level = self.level
        level.name = self.name.GetValue()
        l = int(self.left.GetValue())
        b = int(self.bottom.GetValue())
        r = int(self.right.GetValue())
        t = int(self.top.GetValue())
        level.bounds = (l, b, r, t)
        
class ScaleDialog(BaseDialog):
    def __init__(self, parent, entities):
        self.entities = entities
        super(ScaleDialog, self).__init__(parent, 'Entity Options')
    def create_controls(self, parent):
        grid = wx.GridBagSizer(8, 8)
        text = wx.StaticText(parent, -1, 'Scale')
        self.scale = wx.Slider(parent, -1, 1, 1, 10, size=(128, -1), style=wx.SL_AUTOTICKS)
        self.label = wx.StaticText(parent, -1, '100%')
        self.scale.Bind(wx.EVT_SCROLL, self.on_scroll)
        grid.Add(text, (0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.scale, (0, 1))
        grid.Add(self.label, (0, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        return grid
    def get_value(self):
        return self.scale.GetValue() / 10.0
    def on_scroll(self, event):
        self.update_label()
    def update_label(self):
        label = '%d%%' % int(self.get_value() * 100)
        self.label.SetLabel(label)
    def update_controls(self):
        entity = self.entities[0]
        self.scale.SetValue(int(entity.scale * 10))
        self.update_label()
    def update_model(self):
        for entity in self.entities:
            entity.scale = self.get_value()
            
class PlanetDialog(ScaleDialog):
    def __init__(self, parent, entities):
        super(PlanetDialog, self).__init__(parent, entities)
    def create_controls(self, parent):
        data = [
            ('Earth', 0),
            ('Europa', 1),
            ('Ganymede', 2),
            ('Io', 3),
            ('Jupiter', 4),
            ('Mars', 5),
            ('Moon', 6),
            ('Neptune', 7),
            ('Uranus', 8),
            ('Venus', 9),
        ]
        grid = super(PlanetDialog, self).create_controls(parent)
        text = wx.StaticText(parent, -1, 'Sprite')
        self.sprite = wx.Choice(parent, -1)
        for name, value in data:
            self.sprite.Append(name, value)
        grid.Add(text, (1, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.sprite, (1, 1))
        return grid
    def update_controls(self):
        super(PlanetDialog, self).update_controls()
        set_choice(self.sprite, self.entities[0].sprite)
    def update_model(self):
        super(PlanetDialog, self).update_model()
        sprite = get_choice(self.sprite)
        for entity in self.entities:
            entity.sprite = sprite
            
class ItemDialog(BaseDialog):
    def __init__(self, parent, entities):
        self.entities = entities
        super(ItemDialog, self).__init__(parent, 'Entity Options')
    def create_controls(self, parent):
        data = [
            ('Zipper', 0),
            ('Magnet', 1),
            ('Helmet', 2),
        ]
        grid = wx.GridBagSizer(8, 8)
        text = wx.StaticText(parent, -1, 'Type')
        self.type = wx.Choice(parent, -1)
        for name, value in data:
            self.type.Append(name, value)
        grid.Add(text, (0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.type, (0, 1))
        return grid
    def update_controls(self):
        set_choice(self.type, self.entities[0].type)
    def update_model(self):
        type = get_choice(self.type)
        for entity in self.entities:
            entity.type = type
            
class CircularPathDialog(BaseDialog):
    def __init__(self, parent, entities):
        self.entities = entities
        super(CircularPathDialog, self).__init__(parent, 'Circular Path Options')
    def create_controls(self, parent):
        grid = wx.GridBagSizer(8, 8)
        text = wx.StaticText(parent, -1, 'Period')
        self.period = wx.TextCtrl(parent, -1)
        grid.Add(text, (0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.period, (0, 1))
        text = wx.StaticText(parent, -1, 'Clockwise')
        self.clockwise = wx.CheckBox(parent, -1)
        grid.Add(text, (1, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.clockwise, (1, 1))
        return grid
    def update_controls(self):
        entity = self.entities[0]
        path = entity.path
        if path:
            self.period.SetValue(str(path.period))
            self.clockwise.SetValue(path.clockwise)
    def update_model(self):
        period = float(self.period.GetValue())
        clockwise = self.clockwise.GetValue()
        for entity in self.entities:
            dx = entity.x
            dy = entity.y
            if dx == 0 and dy == 0:
                continue
            radius = (dx * dx + dy * dy) ** 0.5
            angle = math.atan2(dy, dx)
            angle = math.degrees(angle)
            path = CircularPath(radius, angle, period, clockwise)
            entity.path = path
            
class LevelList(wx.ListCtrl):
    INDEX_NUMBER = 0
    INDEX_NAME = 1
    INDEX_STARS = 2
    def __init__(self, parent):
        style = wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL
        super(LevelList, self).__init__(parent, -1, style=style)
        self.project = None
        change_font(self, 10)
        self.InsertColumn(LevelList.INDEX_NUMBER, '#')
        self.InsertColumn(LevelList.INDEX_NAME, 'Name')
        self.InsertColumn(LevelList.INDEX_STARS, 'Stars')
        self.SetColumnWidth(LevelList.INDEX_NUMBER, 32)
        self.SetColumnWidth(LevelList.INDEX_NAME, 128)
        self.SetColumnWidth(LevelList.INDEX_STARS, 48)
    def set_project(self, project):
        self.project = project
        self.update()
    def update(self):
        count = 0
        if self.project:
            count = len(self.project.levels)
        self.SetItemCount(count)
        self.Refresh()
    def update_level(self, level):
        index = self.project.levels.index(level)
        self.RefreshItem(index)
    def get_selection(self):
        indexes = []
        index = -1
        while True:
            index = self.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if index < 0:
                break
            indexes.append(index)
        return indexes
    def get_levels(self):
        return [self.project.levels[index] for index in self.get_selection()]
    def get_level(self):
        levels = self.get_levels()
        if len(levels) == 1:
            return levels[0]
        return None
    def OnGetItemText(self, index, column):
        if self.project:
            levels = self.project.levels
            if index >= 0 and index < len(levels):
                level = levels[index]
                if column == LevelList.INDEX_NUMBER:
                    return '%d' % (index + 1)
                if column == LevelList.INDEX_NAME:
                    return level.name
                if column == LevelList.INDEX_STARS:
                    count = len(level.entities_of_type(Star))
                    return '%d' % count
        return ''
        
class LevelView(wx.Panel):
    def __init__(self, parent):
        super(LevelView, self).__init__(parent, -1)
        self.project = None
        toolbar = self.create_toolbar()
        self.level_list = LevelList(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(toolbar, 0, wx.EXPAND)
        sizer.Add(self.level_list, 1, wx.EXPAND)
        self.SetSizer(sizer)
    def set_project(self, project):
        self.level_list.set_project(project)
    def update(self):
        self.level_list.update()
    def update_level(self, level):
        self.level_list.update_level(level)
    def create_toolbar(self):
        style= wx.HORIZONTAL | wx.TB_FLAT | wx.TB_NODIVIDER
        toolbar = wx.ToolBar(self, -1, style=style)
        toolbar.SetToolBitmapSize((18, 18))
        tool_item(self, toolbar, 'Add', self.on_add, icons.add)
        tool_item(self, toolbar, 'Delete', self.on_delete, icons.delete)
        tool_item(self, toolbar, 'Move Up', self.on_move_up, icons.arrow_up)
        tool_item(self, toolbar, 'Move Down', self.on_move_down, icons.arrow_down)
        tool_item(self, toolbar, 'Properties', self.on_properties, icons.page_white_text)
        toolbar.Realize()
        toolbar.Fit()
        return toolbar
    def post_level_event(self, type):
        level = self.level_list.get_level()
        if level:
            event = Event(self, type)
            event.level = level
            wx.PostEvent(self, event)
    def on_add(self, event):
        event = Event(self, EVT_LEVEL_ADD)
        wx.PostEvent(self, event)
    def on_delete(self, event):
        self.post_level_event(EVT_LEVEL_DELETE)
    def on_move_up(self, event):
        self.post_level_event(EVT_LEVEL_MOVE_UP)
    def on_move_down(self, event):
        self.post_level_event(EVT_LEVEL_MOVE_DOWN)
    def on_properties(self, event):
        self.post_level_event(EVT_LEVEL_PROPERTES)
        
class ScrolledWindow(wx.ScrolledWindow):
    def __init__(self, parent):
        super(ScrolledWindow, self).__init__(parent, -1)
        self.SetBackgroundColour(wx.BLACK)
        self.control = Control(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.control, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.EnableScrolling(True, True)
        self.SetScrollRate(25, 25)
        
class BitmapCache(object):
    def __init__(self):
        self.cache = {}
    def get_bitmap(self, entity, scale, selected):
        key = (
            entity.stroke,
            entity.fill,
            entity.code,
            int(100 * entity.radius),
            int(100 * scale),
            selected,
        )
        if key not in self.cache:
            self.cache[key] = self.create_bitmap(entity, scale, selected)
        return self.cache[key]
    def create_bitmap(self, entity, scale, selected):
        radius = entity.radius * scale
        size = int(radius + scale * 3)
        x, y = size, size
        w, h = size * 2, size * 2
        bitmap = wx.EmptyBitmap(w, h)
        dc = wx.MemoryDC(bitmap)
        dc = wx.GCDC(dc)
        stroke = wx.Color(*entity.stroke)
        fill = wx.Color(*entity.fill)
        dc.SetTextForeground(stroke)
        dc.SetPen(wx.Pen(stroke, scale * 3))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawCircle(x, y, radius)
        tw, th = dc.GetTextExtent(entity.code)
        dc.DrawText(entity.code, x - tw / 2, y - th / 2)
        if selected:
            color = wx.Color(0, 38, 255, 128)
            dc.SetPen(wx.Pen(color, scale * 3))
            dc.SetBrush(wx.Brush(color))
            dc.DrawCircle(x, y, radius)
        del dc
        bitmap.SetMask(wx.Mask(bitmap, wx.BLACK))
        return bitmap
        
class Control(wx.Panel):
    clipboard = set()
    cache = BitmapCache()
    def __init__(self, parent):
        super(Control, self).__init__(parent, -1, style=wx.WANTS_CHARS)
        self.scale = 1
        self.minor_grid = (10, 10)
        self.major_grid = (100, 100) #(120, 80)
        self.show_grid = True
        self.snap_to_grid = True
        self.cursor = (0, 0)
        self.selection = set()
        self.reset_controls()
        self.clear_undo_buffer()
        self.set_level(Level())
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_left_double)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.on_mouse_capture_lost)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
    def on_size(self, event):
        event.Skip()
        self.Refresh()
    def on_paint(self, event):
        dc = wx.BufferedPaintDC(self)
        #dc = wx.PaintDC(self)
        self.draw(dc)
    def set_scale(self, scale):
        self.scale = scale
        self.update_min_size()
        self.Refresh()
    def update_min_size(self):
        scale = self.scale
        l, b, r, t = self.level.bounds
        padding = 25
        width = (r - l + padding * 2) * scale
        height = (t - b + padding * 2) * scale
        before = self.GetMinSize()
        after = (width, height)
        if before != after:
            self.SetMinSize(after)
            self.GetParent().FitInside()
    # Conversion Functions
    def wx2cc(self, x, y):
        s = self.scale
        w, h = self.GetClientSize()
        l, b, r, t = self.level.bounds
        p = (w - (r - l) * s) / 2
        x = l + (x - p) / s
        p = (h - (t - b) * s) / 2
        y = t - (y - p) / s
        return x, y
    def cc2wx(self, x, y, radius=None):
        s = self.scale
        w, h = self.GetClientSize()
        l, b, r, t = self.level.bounds
        p = (w - (r - l) * s) / 2
        q = s * (x - l)
        x = p + q
        p = (h - (t - b) * s) / 2
        q = s * (t - y)
        y = p + q
        if radius is None:
            return x, y
        else:
            radius = radius * self.scale
            return x, y, radius
    # Primitive Rendering Functions
    def line(self, dc, x1, y1, x2, y2):
        x1, y1 = self.cc2wx(x1, y1)
        x2, y2 = self.cc2wx(x2, y2)
        dc.DrawLine(x1, y1, x2, y2)
    def circle(self, dc, x, y, radius):
        x, y, radius = self.cc2wx(x, y, radius)
        dc.DrawCircle(x, y, radius)
    def rectangle(self, dc, l, b, r, t):
        l, b = self.cc2wx(l, b)
        r, t = self.cc2wx(r, t)
        dc.DrawRectangle(l, b, r - l, t - b)
    def clip(self, dc, l, b, r, t):
        l, b = self.cc2wx(l, b)
        r, t = self.cc2wx(r, t)
        dc.SetClippingRegion(l, b, r - l, t - b)
    def text(self, dc, text, x, y):
        w, h = dc.GetTextExtent(text)
        x, y = self.cc2wx(x, y)
        dc.DrawText(text, x - w / 2, y - h / 2)
    # Drawing Functions
    def draw(self, dc):
        dc.SetBackground(wx.BLACK_BRUSH)
        dc.Clear()
        self.draw_grid(dc)
        self.draw_level(dc)
        self.draw_selection(dc)
    def draw_grid(self, dc):
        l, b, r, t = self.level.bounds
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen(wx.Color(32, 32, 32)))
        self.draw_grid_step(dc, self.minor_grid)
        dc.SetPen(wx.Pen(wx.Color(96, 96, 96)))
        self.draw_grid_step(dc, self.major_grid)
        self.circle(dc, 0, 0, 10)
        dc.SetPen(wx.Pen(wx.Color(96, 96, 96), 3))
        self.rectangle(dc, l, b, r, t)
    def draw_grid_step(self, dc, step):
        if not self.show_grid:
            return
        xstep, ystep = step
        l, b, r, t = self.level.bounds
        x = 0
        while x >= l:
            self.line(dc, x, b, x, t)
            x -= xstep
        x = 0
        while x <= r:
            self.line(dc, x, b, x, t)
            x += xstep
        y = 0
        while y >= b:
            self.line(dc, l, y, r, y)
            y -= ystep
        y = 0
        while y <= t:
            self.line(dc, l, y, r, y)
            y += ystep
    def draw_selection(self, dc):
        if self.selecting:
            l, b, r, t = self.get_selection()
            dc.SetPen(wx.Pen(wx.WHITE, 1, wx.DOT))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetLogicalFunction(wx.INVERT)
            self.rectangle(dc, l, b, r, t)
            dc.SetLogicalFunction(wx.COPY)
    def draw_level(self, dc):
        for entity in self.level.entities:
            self.draw_path(dc, entity)
        for entity in self.level.entities:
            self.draw_entity(dc, entity)
    def draw_path(self, dc, entity):
        path = entity.path
        dc.SetPen(wx.Pen(wx.WHITE, 1, wx.DOT))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        if isinstance(path, CircularPath):
            radius = path.radius
            angle = math.radians(path.angle + 180)
            x = entity.x + math.cos(angle) * radius
            y = entity.y + math.sin(angle) * radius
            self.circle(dc, x, y, radius)
    def draw_entity(self, dc, entity):
        selected = entity in self.selection
        bitmap = Control.cache.get_bitmap(entity, self.scale, selected)
        w, h = bitmap.GetSize()
        x, y = self.cc2wx(entity.x, entity.y)
        dc.DrawBitmap(bitmap, x - w / 2, y - h / 2, True)
    # Model Functions
    def set_level(self, level):
        self.level = level
        self.selection.clear()
        self.update_min_size()
        self.clear_undo_buffer()
        self.mark()
        self.Refresh()
    def restore_level(self, level):
        self.level.restore(level)
        self.selection.clear()
        self.changed(False)
    def changed(self, mark=True):
        if mark:
            self.mark()
        self.Refresh()
        event = Event(self, EVT_CONTROL_CHANGED)
        wx.PostEvent(self, event)
    def mark(self):
        level = self.level.copy()
        del self.undo_buffer[self.undo_index + 1:]
        self.undo_buffer.append(level)
        self.undo_index = len(self.undo_buffer) - 1
    def undo(self):
        if self.can_undo():
            self.undo_index -= 1
            level = self.undo_buffer[self.undo_index]
            self.restore_level(level)
    def redo(self):
        if self.can_redo():
            self.undo_index += 1
            level = self.undo_buffer[self.undo_index]
            self.restore_level(level)
    def can_undo(self):
        return bool(self.undo_buffer) and self.undo_index > 0
    def can_redo(self):
        return bool(self.undo_buffer) and self.undo_index < len(self.undo_buffer) - 1
    def clear_undo_buffer(self):
        self.undo_buffer = []
        self.undo_index = -1
    def add_entity(self, entity):
        self.level.entities.append(entity)
        self.changed()
    def cut(self):
        self.copy()
        self.delete()
    def copy(self):
        Control.clipboard = set(entity.copy() for entity in self.selection)
    def paste(self):
        entities = [entity.copy() for entity in Control.clipboard]
        self.selection = set(entities)
        self.level.entities.extend(entities)
        self.changed()
    def duplicate(self):
        self.copy()
        self.paste()
    def delete(self):
        for entity in self.selection:
            self.level.entities.remove(entity)
        self.selection.clear()
        self.changed()
    def select_all(self):
        self.selection = set(self.level.entities)
        self.Refresh()
    def mirror(self, mx, my):
        for entity in self.selection:
            entity.x *= mx
            entity.y *= my
        self.changed()
    def rotate(self, degrees):
        for entity in self.selection:
            dx = entity.x
            dy = entity.y
            if dx == 0 and dy == 0:
                continue
            d = (dx * dx + dy * dy) ** 0.5
            angle = math.atan2(dy, dx)
            angle = angle + math.radians(degrees)
            entity.x = int(math.cos(angle) * d)
            entity.y = int(math.sin(angle) * d)
        self.changed()
    def linear_array(self, count):
        for entity in self.selection:
            x = entity.x
            y = entity.y
            if x == 0 and y == 0:
                continue
            dx = x / float(count - 1)
            dy = y / float(count - 1)
            for i in range(1, count):
                other = entity.copy()
                other.x = int(x - dx * i)
                other.y = int(y - dy * i)
                self.level.entities.append(other)
        self.changed()
    def circular_array(self, count):
        step = math.radians(360.0 / count)
        for entity in self.selection:
            dx = entity.x
            dy = entity.y
            if dx == 0 and dy == 0:
                continue
            d = (dx * dx + dy * dy) ** 0.5
            start = math.atan2(dy, dx)
            for i in range(1, count):
                angle = start + step * i
                other = entity.copy()
                other.x = int(math.cos(angle) * d)
                other.y = int(math.sin(angle) * d)
                self.level.entities.append(other)
        self.changed()
    def get_entity_at(self, x, y):
        entities = self.get_entities_at(x, y)
        if entities:
            return entities[-1]
        return None
    def get_entities_at(self, x, y):
        result = []
        for entity in self.level.entities:
            if entity.contains(x, y):
                result.append(entity)
        return result
    def get_entities_within(self, l, b, r, t):
        result = []
        for entity in self.level.entities:
            if entity.inside(l, b, r, t):
                result.append(entity)
        return result
    def get_selection(self):
        if self.selecting:
            ax, ay = self.selecting
            cx, cy = self.cursor
            l, b = min(ax, cx), min(ay, cy)
            r, t = max(ax, cx), max(ay, cy)
            return l, b, r, t
        else:
            return None
    # Control Functions
    def snap(self, value, size):
        if self.snap_to_grid:
            value = int(round(float(value) / size)) * size
        return value
    def reset_controls(self):
        self.anchor = None
        self.moving = None
        self.selecting = None
    def on_mouse_capture_lost(self, event):
        self.reset_controls()
        self.Refresh()
    def on_mousewheel(self, event):
        if event.ControlDown():
            direction = event.GetWheelRotation()
            direction = direction / abs(direction)
            step = 10.0
            scale = int(self.scale * step)
            scale = max(scale + direction, 1)
            self.set_scale(scale / step)
        else:
            event.Skip()
    def on_key_down(self, event):
        event.Skip()
        code = event.GetKeyCode()
        directions = {
            wx.WXK_UP: (0, 1),
            wx.WXK_DOWN: (0, -1),
            wx.WXK_LEFT: (-1, 0),
            wx.WXK_RIGHT: (1, 0),
        }
        if self.selection and code in directions:
            dx, dy = directions[code]
            if not event.ControlDown():
                dx *= self.minor_grid[0]
                dy *= self.minor_grid[1]
            for entity in self.selection:
                entity.x += dx
                entity.y += dy
            self.changed()
    def on_left_double(self, event):
        x, y = event.GetPosition()
        x, y = self.wx2cc(x, y)
        self.cursor = (x, y)
        if self.selection:
            event = Event(self, EVT_ENTITY_DCLICK)
            event.entities = list(self.selection)
            wx.PostEvent(self, event)
    def on_left_down(self, event):
        self.SetFocus()
        x, y = event.GetPosition()
        x, y = self.wx2cc(x, y)
        self.cursor = (x, y)
        entity = self.get_entity_at(x, y)
        if entity:
            if event.ControlDown():
                if entity in self.selection:
                    self.selection.remove(entity)
                else:
                    self.selection.add(entity)
            elif entity not in self.selection:
                self.selection.clear()
                self.selection.add(entity)
            if entity in self.selection:
                self.anchor = (x, y)
                entities = list(self.selection)
                entities.remove(entity)
                entities.insert(0, entity)
                self.moving = [(e, e.x, e.y) for e in entities]
                self.CaptureMouse()
        else:
            if not event.ControlDown():
                self.selection.clear()
            self.selecting = (x, y)
            self.CaptureMouse()
        self.Refresh()
    def on_left_up(self, event):
        x, y = event.GetPosition()
        x, y = self.wx2cc(x, y)
        self.cursor = (x, y)
        if self.HasCapture():
            self.ReleaseMouse()
        if self.selecting:
            l, b, r, t = self.get_selection()
            entities = set(self.get_entities_within(l, b, r, t))
            if event.ControlDown():
                self.selection ^= entities
            else:
                self.selection = entities
        if self.moving:
            for entity, sx, sy in self.moving:
                if entity.x != sx or entity.y != sy:
                    self.changed()
                    break
        self.reset_controls()
        self.Refresh()
    def on_motion(self, event):
        x, y = event.GetPosition()
        x, y = self.wx2cc(x, y)
        self.cursor = (x, y)
        if self.moving:
            ax, ay = self.anchor
            dx, dy = x - ax, y - ay
            entity, sx, sy = self.moving[0]
            mx = self.snap(sx + dx, self.minor_grid[0]) - sx
            my = self.snap(sy + dy, self.minor_grid[1]) - sy
            for entity, sx, sy in self.moving:
                entity.x = sx + mx
                entity.y = sy + my
            self.Refresh()
        if self.selecting:
            self.Refresh()
            
# Embedded Images
from wx.lib.embeddedimage import PyEmbeddedImage

class icons(object):
    add = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJvSURBVDjLpZPrS5NhGIf9"
        "W7YvBYOkhlkoqCklWChv2WyKik7blnNris72bi6dus0DLZ0TDxW1odtopDs4D8MDZuLU0k"
        "Xq61CijSIIasOvv94VTUfLiB74fXngup7nvrnvJABJ/5PfLnTTdcwOj4RsdYmo5glBWP6i"
        "OtzwvIKSWstI0Wgx80SBblpKtE9KQs/We7EaWoT/8wbWP61gMmCH0lMDvokT4j25TiQU/I"
        "TFkek9Ow6+7WH2gwsmahCPdwyw75uw9HEO2gUZSkfyI9zBPCJOoJ2SMmg46N61YO/rNoa3"
        "9Xi41oFuXysMfh36/Fp0b7bAfWAH6RGi0HglWNCbzYgJaFjRv6zGuy+b9It96N3SQvNKiV"
        "9HvSaDfFEIxXItnPs23BzJQd6DDEVM0OKsoVwBG/1VMzpXVWhbkUM2K4oJBDYuGmbKIJ0q"
        "xsAbHfRLzbjcnUbFBIpx/qH3vQv9b3U03IQ/HfFkERTzfFj8w8jSpR7GBE123uFEYAzaDR"
        "IqX/2JAtJbDat/COkd7CNBva2cMvq0MGxp0PRSCPF8BXjWG3FgNHc9XPT71Ojy3sMFdfJR"
        "CeKxEsVtKwFHwALZfCUk3tIfNR8XiJwc1LmL4dg141JPKtj3WUdNFJqLGFVPC4OkR4Bxaj"
        "TWsChY64wmCnMxsWPCHcutKBxMVp5mxA1S+aMComToaqTRUQknLTH62kHOVEE+VQnjahsc"
        "NCy0cMBWsSI0TCQcZc5ALkEYckL5A5noWSBhfm2AecMAjbcRWV0pUTh0HE64TNf0mczcnn"
        "Qyu/MilaFJCae1nw2fbz1DnVOxyGTlKeZft/Ff8x1BRssfACjTwQAAAABJRU5ErkJggg=="
    )
    
    arrow_down = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAENSURBVDjLpZM/SwNREMTn"
        "xBRpFYmctaKCfwrBSCrRLuL3iEW6+EEUG8XvIVjYWNgJdhFjIXamv3s7u/ssrtO7hFy2fc"
        "OPmd03SYwR88xi1cPgpRdjjDB1mBquju+TMt1CFcDd0V7q4GilAwpnd2A0qCvcHRSdHUBq"
        "AYgOyaUGIBQAc4fkNSJIIGgGj4ZQx4EEAY3waPUiSC5FhLoOQkbQCJvioPQfnN2ctpuNJu"
        "gKNUWYsMR/gO71yYPk8tRaboGmoCvS1RQ7/c1sq7f+OBUQcjkPGb9+xmOoF6ckCQb9pmj3"
        "rz6pKtPB5e5rmq7tmxk+hqO34e1or0yXTGrj9sXGs1Ib73efh1WaZN46/wI8JLfHaN24Fw"
        "AAAABJRU5ErkJggg=="
    )
    
    arrow_left = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAADrSURBVDjLY/z//z8DJYCJ"
        "gUIwyAwoPZHJBsS7STGABY1/9e+fvzKkGMAIiwWgzRfF2ST0/vz5w/Dw/UOGXz9/M/z6Ac"
        "K/GH4CMZj+jmCD5C70X2VkgWo+KcYqrqfArcTw598fBhluOTD9++9fIP7N8PsfEP/9AxUD"
        "0b8ZVq9ci/AC0Nm//zD+Yfj19xdY0R+got9gxb8RNNQAkNyf/0CxX39QvZC5M+68MJuIAQ"
        "czJ8PDlw8ZXr9/g9XZIK+BNP/5/Yfh/sJHjIzIKTF2VchNoEI5oAbHDWk7TpAcjUDNukDN"
        "B4nVjOKFEZwXAOOhu7x6WtPJAAAAAElFTkSuQmCC"
    )
    
    arrow_redo = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAIDSURBVDjLpZJPSJRRFMXP"
        "N46GWqRjZjkOhILU2lXUotzYqglmEQURZLtQbFEK2VLIlQVu2kXQIsOghDaFZS1yI4Vhf3"
        "CcwWSgNlmRY3z3nPu10GxEF2UXHo97ee/AuecXRFGE/6nYvzw+M5LpO3XnRNmWBRjqNI03"
        "S2dBqYXuZ50pp2ckdYhqE1VPCjKBFBprknAKc4XcjbELj3vWCXQ/7TwoqTdZ1ZSurUygur"
        "wa8VgcigS5w11gJJiIN9lpZD/ODTy59KI/DgBd4+dSLu/dnziQbqjeg2UWEQvKQBe0ejzS"
        "Wm9G0FgBAHEAEJVJbm9K11ftBp0ISWQ/v0P+Ux5rFoxo3JWEJMzN54Ynrry8XCrQsXNbDY"
        "q2BMkx/nZ8QdToyNmxi6ULax88PC3j1ET/ZNe6FEi1VZZXIUAMhS8F0Ljh80oKvGvG86Wz"
        "OADQCIoIggAmgiE3jfH51cmBTUFiqKnFH4tYtiISO+pgxsyx60eH/oaNIIoinLx9vKexNj"
        "nUsrcFihxLy0uYnZ9FfiEP2h8ORK30EmaGPwRrFsw4mivkjlSUVaTrEw0IEaK1uRXN+1rg"
        "keDuoAsOh9zx8N7Yegv3Ox8tWMjBV+9fP5jJzuDb1+8o/iyu7EOCuaBI4CpQojZHuf3aoR"
        "RNGZIdMrWRqpMpJgqS4/ftcuRuzQcbBLZSvwCJx2jrjVn/uwAAAABJRU5ErkJggg=="
    )
    
    arrow_rotate_anticlockwise = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAHySURBVDjLtZPvT1JxFMb5"
        "O/gHskVzrrV+mFZomDdEDGkYKSXlRleY6IzcFdQ7lBgYeaELBNjFEpbWi9psRU7JnCa3VY"
        "TV/WfY01davkFk0/XivDp7Ps/Zc86RAZAdpmT/BWDLmun+5ZuS5X0P+paMML82SKZXeroq"
        "YGDttty22it6Po8iWeCxIAlI/5pF9Osj3M8MwPCsXex8ekVeEWAlYn+OxaKUxNx2FKmfcT"
        "zfjiH2ncNsnsfIOzu00RZxT4B1pZee3GTw4vdfVyEfxkTWAdfyMMJfHiL2LYgImcSyeAst"
        "gQt0GeBuxiQl8iEIP/iSW/eCrtiV0rLXkm3s1ThVnN6cQkj0w511osl7TioD9L29QcaNY6"
        "4QhWvlHrrmtey/niasclCcEqrp81B669HoPo0yAEmaBBcpuTOZQegF9S6gdUaJqms0vdRL"
        "3JYXQdEHLueD9snlovpxc2qnd8nfiIues9gXYEx30INLFvAksB1IIPcAd9LdaPY1oEcw4H"
        "qiE2ecJ7DvHegSlGh/Y0FgywP3uhPeDRae9TG4P7nArjHQ8W2oG1KgIkATUcmpYJNonjeC"
        "+TCMyZJwFOMfR+BadaCdo3DcdhRVT5kkTZOkC/VjJ3GKqUNHSA3NTCsR1+BAz1RrPwaFtQ"
        "YH/kZF/5GKa/wDDtK86rC6fMkAAAAASUVORK5CYII="
    )
    
    arrow_undo = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAIJSURBVDjLpVM9aJNRFD35"
        "GsRSoUKKzQ/B0NJJF3EQlKrVgijSCBmC4NBFKihIcXBwEZdSHVoUwUInFUEkQ1DQ4CKiFs"
        "QsTrb5xNpgaZHw2Uog5t5zn0NJNFaw0guX97hwzuPcc17IOYfNlIdNVrhxufR6xJkZjAbS"
        "QGXjNAorqixSWFDV3KPhJ+UGLtSQMPryrDscPwLnAHOEOQc6gkbUpIagGmApWIb/pZRX4f"
        "jj889nWiSQtgYyBZ1BTUEj6AjPa0P71nb0Jfqwa+futIheHrzRn2yRQCUK/lOQhApBJVQJ"
        "ChHfnkCqOwWEQ+iORJHckUyX5ksvAEyGNuJC+s6xCRXNHNxzKMmQ4luwgjfvZp69uvr2+I"
        "ZcyJ8rjIporrxURggetnV0QET3rrPxzMNM2+n7p678jUTrCiWhphAjVHR9DlR0WkSzf4IH"
        "xg5MSF0zXZEuVKWKSlCBCostS8zeG7oV64wPqxInbw86lbVXKEQ8mkAqmUJ4SxieeVhcnA"
        "NFC02C7N2h69HO2IXeWC8MDj2JnqaFNAMd8f3HKjx6+LxQRmnOz1OZaxKIaF1VISYwB9AR"
        "ZoQaYY6o1WpYCVYxt+zDn/XzVBv/MOWXW5J44ubRyVgkelFpmF/4BJVfOVDlVyqLVBZI5m"
        "anPjajDOdcswfG9k/3X9v3/vfZv7rFBanriIo++J/f+BMT+YWS6hXl7QAAAABJRU5ErkJg"
        "gg=="
    )
    
    arrow_up = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAEGSURBVDjLpZM/LwRRFMXP"
        "spmEaGc1shHRaiXsJ5GIRixbCr6SikxIlqgJM5UohIiGdofovHf/PZVmYwZvTntPfjnn3t"
        "xWCAFNNFE33L/ZKXYv+1dRgL3r7bu0PbucJp3e4GLjtsrXGq9wkA8SU7tPk87i/MwCzAyP"
        "5QNeytcnJl46XMuoNoGKDoVlTkQhJpAgmJqcBjnqkqPTXxN8qz9cD6vdHtQMxXOBt49y5X"
        "jzLB/3tau6kWewKiwoRu8jZFvn+U++GgCBlWFBQY4qr1ANcAQxgQaFjwH4TwYrQ5skYBOY"
        "KbzjiASOwCrNd2BBwZ4jAcowGJgkAuAZ2dEJhAUqij//wn/1BesSumImTttSAAAAAElFTk"
        "SuQmCC"
    )
    
    blank = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU"
        "1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAZdEVYdFNvZnR3YXJlAFBhaW50"
        "Lk5FVCB2My41LjVJivzgAAAAFUlEQVQ4T2NgGAWjITAaAqMhAAkBAAQQAAFypRN2AAAAAE"
        "lFTkSuQmCC"
    )
    
    cut = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAIaSURBVDjLY/j//z8DLqya"
        "NVPLrnr5PMnESay41DDgM8Cuellm+7rTT0RiJ3Aii4snTGIiygDnupV5c/dc/QF0AT9MTC"
        "l9hq5P67qtRBng3ri6ZN2Je/9lU6bKgfgSCZPVJ2+7+CR9+u5tRBng07K2+sCVZ//lUqep"
        "CMX0y87cefnO9B2XH4rGTZQgyoCA9vUt5+69/a+QNj25f/O504evPf+jkDbNmuhADOna1H"
        "n50cf/fZvPf7vz8ut/87JFOUTFAq9tHDiUI/u3dd8Fatxy9tH/xCk7FxCMRiGXNCmjzLmr"
        "neo2XtLJmLckffqesxcefPgfP3HbUcHgRha8Bgg5p0kANd5OWHXnf8i8C59TN7/6P3PXjf"
        "8PX//4H965bg+vZbgjXgOMsuasiVt67a+Ub4GdhHeef8LaJ/9n773zf+nZ9//Tt7//H7vs"
        "xn9Zz7QUnAZ4de375Fi3Ahy/RnnTpqdteP6/ZNGpf+kbn/7XjZty0Ld3x2XrgvVfuA08Ob"
        "Aa4NK09XnUkmsvHJvWHU3b9ua/Wd7yG+Y5a14HTj3yGSSvHlZW5lCx/b+QRZA0VgPkgsvD"
        "AqcffxO17MY/s5xlp7lMAyVMM1Y8DF9w8RenlqOcWVbfHPvSLX94jX0FcMaCiGu6hJhHlg"
        "KMrx83/1jypuf//Sftf5q0+u5/o6RFN0jKjTyGXuyGiQuu25dt+26SuuQBj5G3CLoaAMk4"
        "ntedg7qJAAAAAElFTkSuQmCC"
    )
    
    delete = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJdSURBVDjLpZP7S1NhGMf9"
        "W7YfogSJboSEUVCY8zJ31trcps6zTI9bLGJpjp1hmkGNxVz4Q6ildtXKXzJNbJRaRmrXoe"
        "Wx8tJOTWptnrNryre5YCYuI3rh+8vL+/m8PA/PkwIg5X+y5mJWrxfOUBXm91QZM6UluUmt"
        "hntHqplxUml2lciF6wrmdHriI0Wx3xw2hAediLwZRWRkCPzdDswaSvGqkGCfq8VEUsEyPF"
        "1O8Qu3O7A09RbRvjuIttsRbT6HHzebsDjcB4/JgFFlNv9MnkmsEszodIIY7Oaut2OJcSF6"
        "8Qx8dgv8tmqEL1gQaaARtp5A+N4NzB0lMXxon/uxbI8gIYjB9HytGYuusfiPIQcN71kjgn"
        "W6VeFOkgh3XcHLvAwMSDPohOADdYQJdF1FtLMZPmslvhZJk2ahkgRvq4HHUoWHRDqTEDDl"
        "2mDkfheiDgt8pw340/EocuClCuFvboQzb0cwIZgki4KhzlaE6w0InipbVzBfqoK/qRH94i"
        "0rgokSFeO11iBkp8EdV8cfJo0yD75aE2ZNRvSJ0lZKcBXLaUYmQrCzDT6tDN5SyRqYlWeD"
        "LZAg0H4JQ+Jt6M3atNLE10VSwQsN4Z6r0CBwqzXesHmV+BeoyAUri8EyMfi2FowXS5dhd7"
        "doo2DVII0V5BAjigP89GEVAtda8b2ehodU4rNaAW+dGfzlFkyo89GTlcrHYCLpKD+V7yee"
        "HNzLjkp24Uu1Ed6G8/F8qjqGRzlbl2H2dzjpMg1KdwsHxOlmJ7GTeZC/nesXbeZ6c9OYnu"
        "xUc3fmBuFft/Ff8xMd0s65SXIb/gAAAABJRU5ErkJggg=="
    )
    
    disk = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAH+SURBVBgZBcE9i11VGAbQ"
        "tc/sO0OCkqhghEREAwpWAWUg8aMVf4KFaJEqQtAipTZWViKiCGOh2Ap2gmJhlSIWFsFOxU"
        "K0EsUM3pl79n4f12qHb3z3Fh7D83gC95GOJsDe0ixLk5Qq/+xv/Lw9Xd+78/HLX3Y8fXTr"
        "2nWapy4eCFKxG7Fby97SnDlYtMbxthyfzHO//nl85fNvfvnk8MbX5xa8IHx1518Vkrj54Q"
        "+qQms2vVmWZjdiu5ZR2rT01166/NCZg/2PFjwSVMU6yjoC1oq+x6Y3VbHdlXWExPd379nf"
        "7Nmejv2Os6OC2O4KLK0RNn3RNCdr2Z5GJSpU4o+/TkhaJ30mEk5HwNuvX7Hpi76wzvjvtI"
        "wqVUSkyjqmpHS0mki8+9mPWmuWxqYvGkbFGCUAOH/+QevYI9GFSqmaHr5wkUYTAlGhqiRR"
        "iaqiNes6SOkwJwnQEqBRRRJEgkRLJGVdm6R0GLMQENE0EkmkSkQSVVMqopyuIaUTs0J455"
        "VLAAAAAODW0U/GiKT0pTWziEj44PZ1AAAAcPPqkTmH3QiJrlEVDXDt0qsAAAAAapa5BqUn"
        "yaw0Am7//gUAAAB49tEXzTmtM5KkV/y2G/X4M5fPao03n/sUAAAAwIX7y5yBv9vhjW/fT/"
        "IkuSp5gJKElKRISYoUiSRIyD1tufs/IXxui20QsKIAAAAASUVORK5CYII="
    )
    
    door_out = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJCSURBVDjLlZO7a9RBFIW/"
        "+e1ms0kMmOCbRKKGaCBBUCsttNM/wU4UsRQUQQSblIKWFpGIiLVYWQgWsRIRxFc0PhOMhS"
        "jRDZFkZ+5jLFazWWx04HKq883cw5mQc+Z/z9T105fc7ayZLpb/x/j6xpl37jZYWb+Jmdkp"
        "eouKrgDGxsayu/NnzGxFT4xkCpzKuk2s2TaIm5NnXiASWQGYGX19fQCEEFo055f07DsABO"
        "LPeUwiOTsiSrEakMlM1u+tmP+MmeFm1GufkaUFXBLZ7e8X3F++y0KqETqbZgDVhJtgmnBN"
        "QCC7k1K9CZjufcqWjZvpsbXc+jiBqaFimBpX+/eQVXFJmCbIDYDKb8CRK4eeD/QPMDo0ir"
        "qya3An4oqYcPv2HeT3zSaRrHU2rv/K+6ykFCkfvnzw5sCWgdHRoRFq9RpLsoSYkFzoKq9B"
        "1RBJmCqWIt1dP+hdO09baZlFqVPcO/fg2JuPb6cePXtMEUq0l6pUyx1USx1ES6gYInVcIy"
        "aR2vcSs7PriKmtGeLkxYcjB8/vz8v1ZVSVDx9mMHVMDTcnpYir4BIxEeZjGdwRSc0Qt3/d"
        "yUx4S5FLnNt7oaUL+upaIwMVTCMhlHF3VFOzB6rK8eFTZMstHQghkCQ2zBJxSY0e5AagvB"
        "pQFAUndp9q6UAIAZHGCp09/bgKGpcgf8FMCePj43l6epq5ubmW/q/Wo9tn6erupr3aRaXa"
        "SVulncWfNT69efIt/Mt3nji5dYOZ7jCTYTMdcre+olw5ahIXfgHcTaP3d3vNvQAAAABJRU"
        "5ErkJggg=="
    )
    
    folder_page = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJCSURBVBgZBcFBi1VlGADg"
        "5/3Od+/cYWjUTYlRS43Zi1BGuGlVizZB0EJaFf2JNpHgPt1kBf2EXFlEZFFCUJsIsWmhI0"
        "7iqOPM3HvPPed7e57ITAAAcO3mw1wOg2Fo4PbOo6NoGfuL4d7du4tv+r29yz9dfXsemQkA"
        "AK78cD8/vHDKw4Mm0DKtxqZ2fP3bE7/f2vn2wb2d9yoAAMA4psdH6c7DVEpaDc3+fPDG6X"
        "Xnzxy3MS1vXf/u4LMCAACQ6IJZZdqFaRdm0+K/J3NnTnDx3DEb07WPCwAAAEQw6ahB7cKs"
        "Ftt74eb20tN5mtSi3r5+9o/Z5tZWRAFASp8KoSsFiNRastaJErquk6iR5ZWXzn85iQgSkg"
        "hu3NdACE0XTGsRmVoLESGTasiF1q8tH1wx9h1lU8Rzfrz1souvv6gWShQt6YLSMGW9kpmq"
        "VZRsvbGfypYOt3/29O8/XTrO7hcEEoEOHWZoH/xCC1XkrA1z+9t3rPZ2tNXCibPvq1sf2d"
        "zoZBZAyqQU/vn8nOVwIFqJalXU9eedvHAJjUypOXrwlf4ZKWQWhBTq5mtgWja1HPpqlZnj"
        "Qr97DQloDudFP7BcsRpGi34wX/aOv/BYxbuf/Lp7bGOyXi1ltoFAJhptZXNtxXQpxwXtUB"
        "v35fDU7NSb/sWNy6+ehKrPDCOZ5Ej2si1pC5lzOR7J8UAO+3J8hgYAavatDkePtGFCFrKT"
        "OaGtybZBrmT2RE8ZjIsFAKi5WP61ffWd0xIBAAAASMT3tLwN8D9pITwp1Smo1gAAAABJRU"
        "5ErkJggg=="
    )
    
    icon16 = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU"
        "1BAACxjwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpR"
        "PAAAAAlwSFlzAAAN1gAADdYBkG95nAAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLj"
        "UuNtCDrVoAAAF0SURBVDhPnZM7SwNBFEbXgC8SJGijCIIWQRB8NKYUbGyFgCGdhaCYQrAV"
        "xELBBwQLUbASRTSC/gUrK2PciFESCL4xglrZWMjnNzMZHbPZEFw47OTuvWdv7sxaVpkLCa"
        "udxEhXubySz1hUTS4IyOl/BBOFYiEQdFQsYXIdeUCiCrjq1YJxt1Y7mbxGtskGWSR78q3X"
        "QeBpRgviboLDolZVwVkN8LIKvO1wXStin+SYrJMo6ZFCLiJKwHZzYeB+CribBPIx4P1AcT"
        "MKJOt1J+Z9QUvmpCTpBZ6Xfgu1QN73VUfZIVOw+fO3KJiXknM/8LrllIhYZsAs3mW+989c"
        "GLClJL/iFFwGdPEjc4YdA2WwjXzBbmJx3ClQg/wgfrfdUHPIhbh1s0C6G7AbgdsxJUu16g"
        "4a3ARZKUg1O6edGeSB6tPx/lLt+4rOQpq/R0hQnUixzR4tCLt1sMzEIxIiHp3EdQs5MV4Q"
        "qfibMCTiy5wunEKfKfgG6Ny23S+hOP0AAAAASUVORK5CYII="
    )
    
    icon32 = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAARnQU"
        "1BAACxjwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpR"
        "PAAAAAlwSFlzAAAN1gAADdYBkG95nAAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLj"
        "UuNtCDrVoAAAMfSURBVFhHpZddSBRRFMc3FTOJojKQiiwoLKQPfVDow8iiICKhpwhSsoha"
        "it4iipAoi4IgH/IhCJK0InroOSHo3V1MW13tQyXdZcstIgqC6vQ/OzM7c+/M7Nw7u/BnZ2"
        "fOPf/fPffOmdlIpMgPDUZWQOuLTBNuOIy7oD8QQU+h0nCZQoyCWbtpzOaWjodIpT8Ehkuh"
        "OQ+AmH62ECNgfMfD3KrCmhAp1YfAeCX0qwDAafVsISJh3COYj6x17gE+fh4irdoQJK+Bfu"
        "cBYqVEmW6i+EInBO+NErWMjigMqoZ2QPugFqgR2mCeX8ChOH4ozH58D9HXZ0RjjXIVGpQB"
        "mBZ6AP0rsK5s8Fe4Hisj+txjAEydkAEu6AAcDjCWkxu/3x00zFmZu3JMGjH3oCi0m6voC4"
        "SLHdoAb6qJ5nptAIYYXuUNajepLHxeQTegpjyQucbfXeWd2E80sZcouY1odAvR241EiTrM"
        "/ADRl/uiOQNMR4MA5Osv4FmeA8HBUdceSGwiyva5jayye30zRO62LFGFaXNW4rJrKRKb9S"
        "EYjJcndR1VOUP0/hAqh8nYS+E8jgp7w1wfMTiB8mcf61XCWZ3UNb/9kYHfctfmxMlbLtpk"
        "sz4AV4H30eA8r9lPwaOu0J1x2wWRuqoOwbFDVX5lf4LcSwL7BILErjfZrgYwc5GIW7R7zW"
        "dwrjXQ2ApA8CMhCScudAdY14ZXy+bcQfkBtkjHfDEG/MwDxCvU74bYfCfAN+RoVjZ2zJ5b"
        "qJ1ovEVt9lyFoWVOgGltc7MxxQWAdJcNMNtpdEdux6P1ROmbIhx3TBuey1+pBYEBDYI5ry"
        "nPbPYK2nGte3Pxhps8ZkPwI1rcgFt1AcT3vbEm4zng3cns88md2Cf9gGmTY4/oAnwMNPOD"
        "GVmH9ntKBuhUBuDWqGDO9/NZqAYacMXHymWAXh0A/pvlV+4Urp2HKhx3Sxl+dwdADygDmH"
        "fASynhB/w+B+XeC70+uHYSsl9WxUm81gWoNBNewvcuSOn/HuK2Q588qtGnBVBMMMyroH7I"
        "esH9geP6YnKGGgvTWqgV8n8ZNTP/By7HbilStTvdAAAAAElFTkSuQmCC"
    )
    
    icon_asteroid = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAICSURBVDiNhZNNaxNRFIafjGlTowk1aZPGScnQVpuiE0lVxJUDBcWlG8EP6D9wp6"
        "AgKi4EV/4FQdCV0KWSxeBClGqqnYIJNjKi08Q2TolpTUnTxMU405na4Lu693zde97zHl+n"
        "08ENRZZk4DJwEjgOdIB3wCzwTNV0zR3vswsosiQAN4B7QC+7owncAR6qmt52CiiytAd4AU"
        "wBZEeGSCcHORgJAVA26xSNKu9LZbvQS+C8qult/1/DdWBqf18vF06nGR2KeJ4NiVEOi1GO"
        "pGI8f/2JtY3mWeAa8Mh35mgqDXwAAleVDGMJb/JOLJZNnqjzAL+BYwJwEQjIqfg/ybmPXy"
        "gaVY9tLBFBTsUBgsAlAYtt0skBT2Cj2aK2vkF+u28H42LUPk4KwAnAIczGwtdlMlKccDDA"
        "Sm3d4xOjIU+BXTGvV2g0W/T1+Jn9vNQtDAFLJCyZdcf4o7bGgX17CQcDjCYiGOYvNre2HL"
        "/x04nNC1gKo/B9m6y5UoVT4yJSrB8p1s/E8CCavuz4XcTmPWO8omQ49J8xFo0qT18tADSA"
        "jKBqegG4CzDzpkCpsto1uVRZZeZt0b7eUjV90S3lHKAAZEcSTAwPkIyGrZ7NOoVvK24p54"
        "Bzqqa33cvkB24Ct4GeLp/YBO4DD1RNb4FrG20ospQBpoFJIIu1znNAHni8c53/AEkvt5Js"
        "x5XiAAAAAElFTkSuQmCC"
    )
    
    icon_bumper = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAIQSURBVDiNfZNLa1NRFIW/m3ubSGLzkqRNfKA0akKblrYqDoWCIhTBifgo+A+cKS"
        "hIjzgQHPkXBMGOxA6V/gJNa2uFm0CCRmhMNNTc2KZJk9zjIMltUpqu2Tl7n7X3OnttRUpJ"
        "N5SYiAN3gYvANCCBBPAZWJC6WO/J7xAoMWEDHgHPADsHYxeYB15KXZgWgRITKvABmAE4dn"
        "IS71AUpzcMQMX4hVFIUfy53CH6CFyXujC19sVDYEZzHOX0xE3cgZGesp7gIJ7gOXyhUb6v"
        "vqNR27oKPABeKUTno8Aq4IhcmsMdiPTpvoXynzTpT28AKsCEBtwCHP5wvOdxdu09jUYVVR"
        "3AFxrDM3QeAHcggj8cZzO37gTu2Nq/jWc42lOpulVkZPo2p+I3KGYTmM3dPUltMmBKAy4A"
        "uDzhHgIpm/zNfaNZr3JkMIhN3RuM03vcIrAdKhiQSKr/flPb3jwwrtEyyey2kcPu9FkBRV"
        "HxhccAMBs1dsp5HC4/AJXSRidtRaPlsFkjn8QXGrUIzGadzPICCgo21U7wzGUrViqkLIJ9"
        "Y7yHO3D2UElGIUUm8RZgBxi3SV0kAQHwY22RcjHT93G5mCH7dbFzfCJ1ke628hJwBdpWHo"
        "7h8p5oaTY2KOWT3VZeAq5JXZjdy6QBj4GnwECfJurAc+CF1EUDuraxAyUmxoH7wBQwSWud"
        "vwArwOv96/wfMJW8MAlPZZIAAAAASUVORK5CYII="
    )
    
    icon_item = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAGrSURBVDiNpdPPalNhEAXwX67VgrZm33SXkCbUq72N7oWC4rIbQSn4Bu4UFKRXXA"
        "iufAWhohQsxp3SN9BGIYKJvemu6To0Kv6h10WamhgLBc9qvmHmzHzDOZk0TQ0iE2dDXMcF"
        "VJDiHd7ieRp36kP1fYJMnA1wG/dxwr/xA8t4lMadvQOCTJw9htdYgLkoUi6VTE1NgfbOjm"
        "azqbax0Sd6gytp3Nkb20/cwsKpiQmLi4vy+fzQ2OLkpGKx6MzsrBdra750u5dwE48zlk+X"
        "8AHjS0tL8oXCIdv3kCSJpysr8BXnAlzFeBiGI81JkvjcbA7lCoWCMAzhJK4FetdWKpVGpn"
        "V3d+12uyP54sxMP5wPcB4HBzsKcrncEMF/IdATiXa7feSm7e3tflgL9BSm0WgcmaD557C1"
        "AKv4Xq/XJZubQ4VzUaRSqYw0f6zX4RueBWncaSCGl9WqrVbr0MlbrZZX1Wr/eTeNO8mglN"
        "dxEaIoUi6X5aanZfb//KnRGJTyOi6ncWdv0ExjuIN7OH7IEj/xAA/TuPOLATf2kYmzZ3ED"
        "84j07PweNTz5286/Aam8nSk4CxBkAAAAAElFTkSuQmCC"
    )
    
    icon_planet = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAHVSURBVDiNdZNPyxJRFMZ/zoy+Iig6Mzq6cykyGU219/JCEbQOatM3aFdQEBUtgt"
        "pE36BV8X6DIrgfoLA08A+0l9FhZjFgOPmnhY44vvqs7j08z3nOPfec1Hq9Zh9CiCvAA+Am"
        "cB1YAz+A78BnKeXvfX4qTiCEUIAnwCsgw3FEwAvgrZRytUsghFCBL8A5QLVapVwuk8/nAQ"
        "jDEM/zGI/HcaKvwB0p5UrbBh4D55lMhkajga7rCVvDMDAMg0qlwmAwIIqiW8Aj4H2q3W43"
        "gF/AWavVuiQ+hO/79Ho9gBlwVQPuAWeWZSXEw+GQxWIBQC6Xo16voygKuq5jWRau6+aA+8"
        "q225immXCazWbYto1t26TTaVzXTTxpC0cBbgC7hh1itVoxn8/JZrO72B7X0Y6qgOVySb/f"
        "R1VVisUipVLpKE9jMyR3wzBMuKiqSrPZPCoKwzA+dhQ2E4bneaeKuYQ9bkcBLoC567r4vr"
        "8jOY5zUjyZTAD+Ap8UKeUQeAmbrwuC4KRzEASMRqP4+kxK+Sdu4jvgdhRF7W63S61WwzRN"
        "CoXC7s3T6XR/lL8BHyC5TBrwFHgOpE8U8Q94DbyRUi4SCWIIIVrAQ8ABrrFZ559AB/h4uM"
        "7/ATXMrUC+gI6IAAAAAElFTkSuQmCC"
    )
    
    icon_rocket = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAH+SURBVDiNdZNBbxJhEIafb0FLqAaPBbyxrhC6tVS9Y0o03qAmJsom/gNvmmhiuo"
        "0HE0/+BRMbudS05aTpP1ARwqGspXvblaQkHBC1Fvk80N0spLynmW9m3pnMN6+QUhKEKYQO"
        "PARuAtcBCXwBPgMVU8pmMF94BKYQCvAU2ADOczb+AuvAa1PKkU9gChECPgKrALnlZdKZDI"
        "lEAoAfrotlWXyt1TyiT8BdU8pR+PThCbB6YX6eUqlEKpWaaHtR09A0jeziIh+2tvg5GNwG"
        "HgNvxDqkgTowZxgG6lTxNNrtNu82NwF+AdfCwH1gTtd1v7jf71OtVolGo/wbjYjFYtzK5w"
        "mFQqiqiq7rNJvNKPBAOd026XTa73IyHBKJRCgWi9xbWwPg+8GBH7+qaZ65ogA3AH9hHv4c"
        "H9PtdnFdl+7REZdiMT+WTCZ9gjAz0Ov1qNfrdDodNE0jHo+fmacwPhJc150IxBcWKBQKGI"
        "aBbdsMBgM/5jiOZ9YUxhdGq9WaNQzZbJZGo+H7lmX5BBPfWC6XuaKqM4m84veVCsBvYEkx"
        "pWwBJsDO9jaHtj2z+NC22dnd9dznppTt4CnvAXmAXC5HJpPhcjIJQuA4Dq39/eAp7wF3TC"
        "lHQTGFgWfAC+DcjCFOgJfAK1PKIQTU6MEUYgl4BKwAOcZy/gbUgLfTcv4PpnC+OIFzNzYA"
        "AAAASUVORK5CYII="
    )
    
    icon_star = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAA"
        "lwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vu"
        "PBoAAAHPSURBVDiNbdPLS1VRFAbw3zlagtljUoaWiK+UUtNq1KS4kQgNjKDoAf0HzQoKwh"
        "MNgkb9Cw4CB0UPIlAujqJJYoVUanIzRUGbVRr0uKfB8XrulfvBhr33Wt+3N2t9K4jjWAmi"
        "oBOXcAxHEGMcbzAsiieL04MNgSgIcQN3sFV5/MYg7ovifCoQBRUYQQa0H6apgz11CW1lib"
        "lpPk4UhEbRL4rzlesX15FRvY3MWfY3l77b2JaslkNkH7O2ehrX8CCIB7XjHaqcuULDJvJm"
        "zM/y4iGsobsS51GltbOU/HWGmUmCgAPd6a8aWmjt5PNkNS6GkmrT1J6S/+X5MM6pc5wcYO"
        "o9+aJuNbYVdr0hjoLddWlCRUhQwesRlufJDBAGaby2vkSgPPov0HyQL9M8G0p+VQahxCR8"
        "W0pvf/7g1Qh793G8jx27WP2expcXC7uJUOIwclNpQs12tlYx+ojsE2p2JiIFzE1vCGxq4+"
        "WkygXEyOeTmhSTXw7DL3SFongKERh7ykIuTQ6UkhdyjD0vnG6J4tliK2dxAnT0JFaurU9U"
        "VhbJfSq2chZ9ojhfPEyVuInb2KI8/uAu7onivxRPYwFR0IWr6EXPeiXeYgJDm8f5P+Ullp"
        "9jclUOAAAAAElFTkSuQmCC"
    )
    
    page = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAINSURBVBgZBcG/r55zGAfg"
        "6/4+z3va01NHlYgzEfE7MdCIGISFgS4Gk8ViYyM2Mdlsko4GSf8Do0FLRCIkghhYJA3aVB"
        "tEz3nP89wf11VJvPDepdd390+8Nso5nESBQoq0pfvXm9fzWf19453LF85vASqJlz748vIn"
        "b517dIw6EyYBIIG49u+xi9/c9MdvR//99MPPZ7+4cP4IZhhTPbwzT2d+vGoaVRRp1rRliV"
        "vHq+cfvM3TD82+7mun0o/ceO7NT+/4/KOXjwZU1ekk0840bAZzMQ2mooqh0A72d5x/6sB9"
        "D5zYnff3PoYBoWBgFKPKqDKqjCpjKr//dcu9p489dra88cydps30KswACfNEKanSaxhlnt"
        "jJ8Mv12Paie+vZ+0+oeSwwQ0Iw1xAR1CiFNJkGO4wu3ZMY1AAzBI0qSgmCNJsJUEOtJSMa"
        "CTBDLyQ0CknAGOgyTyFFiLI2awMzdEcSQgSAAKVUmAeNkxvWJWCGtVlDmgYQ0GFtgg4pNt"
        "OwbBcwQy/Rife/2yrRRVI0qYCEBly8Z+P4qMEMy7JaVw72N568e+iwhrXoECQkfH91kY7j"
        "wwXMsBx1L93ZruqrK6uuiAIdSnTIKKPLPFcvay8ww/Hh+ufeznTXu49v95IMoQG3784gYX"
        "dTqvRmqn/Wpa/ADFX58MW3L71SVU9ETgEIQQQIOOzub+fhIvwPRDgeVjWDahIAAAAASUVO"
        "RK5CYII="
    )
    
    page_copy = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAIpSURBVDjLddM9aFRBFIbh"
        "98zM3WyybnYVf4KSQjBJJVZBixhRixSaShtBMKUoWomgnaCxsJdgIQSstE4nEhNREgyoZY"
        "hpkogkuMa4/3fuHIu7gpLd00wz52POMzMydu/Dy958dMwYioomIIgqDa+VnWrzebNUejY/"
        "NV6nQ8nlR4ufXt0fzm2WgxUgqBInAWdhemGbpcWNN9/XN27PPb1QbRdgjEhPqap2ZUv5+i"
        "OwvJnweT1mT5djZKjI6Ej/udz+wt1OJzAKYgWyDjJWyFghmzFsbtcY2gsTJwv09/Vc7RTg"
        "AEQgsqAKaoWsM8wu/z7a8B7vA8cHD3Fr+ktFgspO3a+vrdVfNEulJ/NT4zWngCBYY1oqSg"
        "hKI465fvYwW+VAatPX07IZmF7YfrC0uDE8emPmilOFkHYiBKxAxhmSRPlZVVa2FGOU2Ad2"
        "ap4zg92MDBXJZczFmdflx05VEcAZMGIIClZASdesS2cU/dcm4sTBArNzXTcNakiCb3/HLR"
        "sn4Fo2qyXh3WqDXzUlcgYnam3Dl4Hif82dbOiyiBGstSjg4majEpl8rpCNUQUjgkia0M5G"
        "VAlBEBFUwflEv12b/Hig6SmA1iDtzhcsE6eP7LIxAchAtwNVxc1MnhprN/+lh0txErxrPZ"
        "VdFdRDEEzHT6LWpTbtq+HLSDDiOm2o1uqlyOT37bIhHdKaXoL6pqhq24Dzd96/tUYGwPSB"
        "Vv7atFglaFIu5KLuPxeX/xsp7aR6AAAAAElFTkSuQmCC"
    )
    
    page_delete = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJ2SURBVBgZBcFLiJVlGADg"
        "5/3+b87cbLyFNBJ4oexGQYqIi6hFQambgohoE0aLUqGCaBcuonWLUFe1CIJolWCLaiK1C0"
        "FUREpRBgmWNpqi4XjOnP97e57ITI+8fuLZ6bnJZ0rYhikECGSQzbi1M1cu5UJcvfzqycN7"
        "RgCRmXa9+dXJ9w5su6uUWJV0EoBMSIv/LXv/uyvOnx1eP/3zL2u+PLxnCBVKF3cMarfq1D"
        "+6EkGQjT6b8TgtLfceuv0mO7ZU37bFmWx3Xn5w/7HVx9/ePSwQESsysxt0xUShBl2hCyIo"
        "As383MCe7fM23jY5Xedm34UCSUBBCUqEEqFEKBFKF/7+d8mGFcvuXhOe37lWN9E9CRUgk9"
        "oRQkZofVJC7Rhk8fulNGpjrY08sHlS1DKGCpkkahQpJaKEQDayKwwoLbTWSYUooEKiIYIQ"
        "EolsTHSAKKIPWVJDJlChjcmkIZCZoBS0ULskgySFvtE3oEJrKTNJUgKQQAj950eMFg5ZPv"
        "ebU+vW2zH9WGWnCn2jT7LRACRoyY2FI6ZOfeC+p54zuekeSz99YubkQv304YkDFdo4tUwH"
        "fxgJqQWZQSMjPX30Lbv3vmDqzBeceMPMylU2b9jg+1/z5Qrjca/vmZ+bsHVd0ZI+6YOWrL"
        "7yp6lbNrHrFQD14LyuxcYK42Fr49Zy1ItvzvVapBSgJetXzrv+4zGzR180XDrvOq5d7fSd"
        "vyos3+gvzA66m1+7dzSbmUXSACunq4vn9zt9/B23rp5WuwnXFsf+uNBJ/aHITNv3fbZvvJ"
        "yPR8T9KWcAJImUHh0eq1sXP+zWDi/G1cHc8Oxgy8cvffT1E/8D2iAtJW5RUGAAAAAASUVO"
        "RK5CYII="
    )
    
    page_paste = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJRSURBVBgZBcExiJZlHADw"
        "3/O+732enKYdQVeklWBeoSBFtmgNNrRcQ9DSFBQZDU4OEYSNbQUtCg5FEAUpDdXSUliBQR"
        "BEBBXeVuFZnvKd1/e9z/P/9/uVzATnX37wEfwCAICbpy6s7wUAACjnXnrgUbyFtV3Ld3vh"
        "jbO2rv8Alu465sOzr9veugUf4dKpC+sXAWDApWdeObNv+Z57/fPV+zJTm22BzHTiyD5LR0"
        "/KzLXPzr/3LC4CwID7l1fus/n7FTHetv7JO2QiXc8fpbTx83eWV4/tBgCAAbLORR11+w+L"
        "VmWmj9tpLUMEcPO3LeX401599/O8MVv59c/1vx67fG5te4Boo6ijGGfa7D+kNoQ3n1u1MQ"
        "0FkWlsYeiP+ODK5sN96a8++doXBweIOhOtkqEUMum7zo3b6Y+N1HVprOHWdvXUQzsdP7TX"
        "0qRb+TbbTx1EnYs618a5qE3UBvrC4sCkLyZ9sTjpXNvcduhOXnxijzrmgQFinMlxLmuIsZ"
        "GpLaZSWOjJJPticehc/TdN/555fP8OC0NngKhzUZsYm6hBpMhUFH3XASVFJDt6pSv6vpcY"
        "IMcm503UJmojgABFEfrCZOiUTBFFKUUmA9SxamMTrYmxkURLBUNHVzqR9IUuMGHnQGYaIO"
        "dVjE22JmvISNCiYgAAAJGVKAZc3p5OT+zatyprE7WRicGsTrEXAADM6lSJrgx4++svP92N"
        "owBw7fDzFroD9iyOMulKUQpQ0Hd3iKzzkpkAAODkme+/6btykG6F3KIgQVFKZJvuWVrY+T"
        "+vNUkTODP9hQAAAABJRU5ErkJggg=="
    )
    
    page_white_text = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAADoSURBVBgZBcExblNBGAbA"
        "2ceegTRBuIKOgiihSZNTcC5LUHAihNJR0kGKCDcYJY6D3/77MdOinTvzAgCw8ysThIvn/V"
        "ojIyMjIyPP+bS1sUQIV2s95pBDDvmbP/mdkft83tpYguZq5Jh/OeaYh+yzy8hTHvNlaxNN"
        "czm+la9OTlar1UdA/+C2A4trRCnD3jS8BB1obq2Gk6GU6QbQAS4BUaYSQAf4bhhKKTFdAz"
        "rAOwAxEUAH+KEM01SY3gM6wBsEAQB0gJ+maZoC3gI6iPYaAIBJsiRmHU0AALOeFC3aK2cW"
        "AACUXe7+AwO0lc9eTHYTAAAAAElFTkSuQmCC"
    )
    
    shape_flip_horizontal = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAElSURBVDjL3dM9SgNRFAXg"
        "M/kxPjQRLQIWFoHZTSAuwNbOeiCNbsBmQBBEmyCCLsJCQbEVwcI0KUxpKZlJ7jnXwomNip"
        "Fg41nA9947977I3TFPSpgzfwOc3Y3D6W3eB4C9i2F/9/w5/AogPTEhBgDJY8qTmYHeTd4y"
        "edf4Xq4kkOomvUFrJsDo6fpKKUwBk2NjrRKMSn8ETq6zdiNEnUYtwhQghVAGVpfKnZ2jp/"
        "a3wPFVFoye1msRcgNM0xsJrxmxWAbMlG4fPIYvAaMnzXoprpYBo4MqnmDCaCyYEc1GNTYq"
        "+QQcXo5aRu8uL0SYFKdT04kQ2ZgY5QLkINXd2r//KLRSFJVSCA/DCeiABKhYcaMweMkgCp"
        "RD7kHyFMAmAET/9C/8Jm9+37CM1tkN3AAAAABJRU5ErkJggg=="
    )
    
    shape_flip_vertical = PyEmbeddedImage(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAAB"
        "l0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAE0SURBVDjLtZHPSgJRGMXd"
        "zmPM88w+gqBF0KZF0CIIstkkhVhSIGFYYWHSHxKmCSdhYAiCIEJTk4ibNJbUA1jjXDenMy"
        "+gzkSLD+7i/s4533diAGJ/mVCfs05fzdieEVpg76avENYJe1uVH4QSIKwRFqUHH3ZzgI3y"
        "93gC+VtfJWyc3fuw6hL2k4T1KJG8GiFQuJMKYZ2wZ9YknNYAlYZEmW+zKrF22RsuQFgQBm"
        "ODOyPYOYgdOAdwwughcgsja1w56WocwcFy8QNLhQ4WD10sHLQxnxOYy75gNvM8PAFhhbBO"
        "2Nu1PlF0vrB/3cWO+Y70hYuZ7dZ4K9BZpbOROHWxWeogdf6G1eM2ptONcDdgbI2xRfzoFf"
        "G8wFSqHv6IjK3QWSfsTSZr0VsgrE6sV43/qzHK/AJ0lPqXO1KzBQAAAABJRU5ErkJggg=="
    )
    
# Main
def main():
    app = wx.PySimpleApp()
    frame = Frame()
    frame.Show()
    app.MainLoop()
    
if __name__ == '__main__':
    main()
    