import wx
import wx.aui as aui
import functools
import json
import math
import os
import sys
import icons

try:
    import Image
except Exception:
    pass
    
json.encoder.FLOAT_REPR = lambda x: format(x, '.2f')

TITLE = 'Star Edit'
DEFAULT_NAME = '(Untitled)'
DEFAULT_BOUNDS = (-240, -160, 240, 160)
DEFAULT_SCALE = 0.5

RADIUS_ASTEROID = 32
RADIUS_BUMPER = 64
RADIUS_ITEM = 16
RADIUS_PLANET = 64
RADIUS_ROCKET = 20
RADIUS_STAR = 12

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
    
def wx2pil(image):
    width, height = image.GetWidth(), image.GetHeight()
    data = image.GetData()
    return Image.fromstring('RGB', (width, height), data)
    
def pil2wx(image):
    width, height = image.size
    data = image.tostring()
    return wx.ImageFromData(width, height, data)
    
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
    @property
    def draw_path_key(self):
        path = self.path
        if isinstance(path, CircularPath):
            dx = self.x - path.x
            dy = self.y - path.y
            radius = (dx * dx + dy * dy) ** 0.5
            return (CircularPath, int(path.x), int(path.y), int(radius))
        else:
            return None
            
class CircularPath(object):
    def __init__(self, x, y, period, clockwise):
        self.x = x
        self.y = y
        self.period = period
        self.clockwise = clockwise
    @property
    def key(self):
        result = {
            'type': PATH_CIRCULAR,
            'x': self.x,
            'y': self.y,
            'period': self.period,
            'clockwise': self.clockwise,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key['x']
        y = key['y']
        period = key['period']
        clockwise = key['clockwise']
        return CircularPath(x, y, period, clockwise)
    def copy(self):
        return CircularPath(self.x, self.y, self.period, self.clockwise)
        
class LinearPath(object):
    def __init__(self, x, y, period):
        self.x = x
        self.y = y
        self.period = period
    @property
    def key(self):
        result = {
            'type': PATH_LINEAR,
            'x': self.x,
            'y': self.y,
            'period': self.period,
        }
        return result
    @staticmethod
    def from_key(key):
        x = key['x']
        y = key['y']
        period = key['period']
        return LinearPath(x, y, period)
    def copy(self):
        return LinearPath(self.x, self.y, self.period)
        
class Rocket(Entity):
    radius = RADIUS_ROCKET
    @property
    def image(self):
        return icons.rocket.GetImage()
    @property
    def image_key(self):
        return Rocket
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
    def __init__(self, x, y, scale, sprite):
        super(Planet, self).__init__(x, y)
        self.scale = scale
        self.sprite = sprite
    @property
    def image(self):
        images = [
            icons.planet1,
            icons.planet2,
            icons.planet3,
            icons.planet4,
            icons.planet5,
            icons.planet6,
            icons.planet7,
        ]
        return images[self.sprite].GetImage()
    @property
    def image_key(self):
        return (Planet, int(self.scale * 100), self.sprite)
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
    def __init__(self, x, y, scale):
        super(Bumper, self).__init__(x, y)
        self.scale = scale
    @property
    def image(self):
        return icons.bumper.GetImage()
    @property
    def image_key(self):
        return (Bumper, int(self.scale * 100))
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
    def __init__(self, x, y, scale):
        super(Asteroid, self).__init__(x, y)
        self.scale = scale
    @property
    def image(self):
        return icons.asteroid.GetImage()
    @property
    def image_key(self):
        return (Asteroid, int(self.scale * 100))
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
    radius = RADIUS_ITEM
    def __init__(self, x, y, type):
        super(Item, self).__init__(x, y)
        self.type = type
    @property
    def image(self):
        images = [
            icons.item_zipper,
            icons.item_magnet,
            icons.item_shield,
        ]
        return images[self.type].GetImage()
    @property
    def image_key(self):
        return (Item, self.type)
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
    radius = RADIUS_STAR
    @property
    def image(self):
        return icons.coin.GetImage()
    @property
    def image_key(self):
        return Star
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
        self.set_default_size()
        self.Center()
        set_icon(self)
        if len(sys.argv) == 2:
            self.open(sys.argv[1])
        else:
            self.new()
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
        menu_item(self, menu, 'Import Levels...', self.on_import)
        menu_item(self, menu, 'Export Bitmap...', self.on_export_bitmap)
        menu_item(self, menu, 'Export All Bitmaps...', self.on_export_all_bitmaps)
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
        menu.AppendSeparator()
        for cls in (Rocket, Star, Planet, Bumper, Asteroid, Item):
            name = cls.__name__
            func = functools.partial(self.on_select_all, cls=cls)
            menu_item(self, menu, 'Select All - %ss' % name, func)
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
        menu_item(self, menu, 'Delete Path', self.on_delete_path)
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
        self.path = None
        project = Project()
        self.set_project(project)
        self.unsaved = False
    def open(self, path):
        self.path = path
        project = Project.load(path)
        self.set_project(project)
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
        if self.confirm_close():
            self.new()
    def on_open(self, event):
        if self.confirm_close():
            dialog = wx.FileDialog(self, 'Open', wildcard='*.star', style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
            if dialog.ShowModal() == wx.ID_OK:
                path = dialog.GetPath()
                self.open(path)
            dialog.Destroy()
    def on_import(self, event):
        dialog = wx.FileDialog(self, 'Import', wildcard='*.star', style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            project = Project.load(path)
            self.project.levels.extend(project.levels)
            self.level_view.update()
        dialog.Destroy()
    def on_save(self, event):
        if self.path:
            self.project.save(self.path)
            self.unsaved = False
            return True
        else:
            return self.on_save_as(None)
    def on_save_as(self, event):
        dialog = wx.FileDialog(self, 'Save', wildcard='*.star', style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            self.path = path
            self.project.save(path)
            self.unsaved = False
            dialog.Destroy()
            return True
        else:
            dialog.Destroy()
            return False
    def get_bitmap_name(self, level):
        index = self.project.levels.index(level)
        name = ''.join(c for c in level.name if c.isalnum())
        return '%d - %s.png' % (index + 1, name)
    def on_export_bitmap(self, event):
        name = self.get_bitmap_name(self.control.level)
        dialog = wx.FileDialog(self, 'Save', wildcard='*.png', defaultFile=name, style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            bitmap = self.control.create_bitmap()
            bitmap.SaveFile(path, wx.BITMAP_TYPE_PNG)
        dialog.Destroy()
    def on_export_all_bitmaps(self, event):
        dialog = wx.DirDialog(self, 'Select Directory', style=wx.DD_DEFAULT_STYLE|wx.DD_DIR_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            base = dialog.GetPath()
            for level in self.project.levels:
                self.show_page(level)
                name = self.get_bitmap_name(level)
                path = os.path.join(base, name)
                bitmap = self.control.create_bitmap()
                bitmap.SaveFile(path, wx.BITMAP_TYPE_PNG)
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
    def on_select_all(self, event, cls=None):
        self.control.select_all(cls)
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
        entities = list(self.control.selection)
        dialog = LinearPathDialog(self, entities)
        if dialog.ShowModal() == wx.ID_OK:
            self.control.changed()
        dialog.Destroy()
    def on_circular_path(self, event):
        entities = list(self.control.selection)
        dialog = CircularPathDialog(self, entities)
        if dialog.ShowModal() == wx.ID_OK:
            self.control.changed()
        dialog.Destroy()
    def on_delete_path(self, event):
        self.control.delete_path()
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
            ('Generic (Brown)', 0),
            ('Saturn (Warm)', 1),
            ('Earth', 2),
            ('Generic (Purple)', 3),
            ('Saturn (Cool)', 4),
            ('Sun', 5),
            ('Europa', 6),
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
            ('Shield', 2),
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
            
class LinearPathDialog(BaseDialog):
    def __init__(self, parent, entities):
        self.entities = entities
        super(LinearPathDialog, self).__init__(parent, 'Linear Path Options')
    def create_controls(self, parent):
        grid = wx.GridBagSizer(8, 8)
        text = wx.StaticText(parent, -1, 'Period')
        self.period = wx.TextCtrl(parent, -1)
        grid.Add(text, (0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.period, (0, 1))
        return grid
    def update_controls(self):
        entity = self.entities[0]
        path = entity.path
        if path:
            self.period.SetValue(str(path.period))
    def update_model(self):
        period = float(self.period.GetValue())
        for entity in self.entities:
            entity.path = LinearPath(0, 0, period)
            
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
            entity.path = CircularPath(0, 0, period, clockwise)
            
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
            entity.image_key,
            int(100 * scale),
            selected,
        )
        if key not in self.cache:
            self.cache[key] = self.create_bitmap(entity, scale, selected)
        return self.cache[key]
    def create_bitmap(self, entity, scale, selected):
        if hasattr(entity, 'scale'):
            bitmap_scale = scale * entity.scale / 2.0
        else:
            bitmap_scale = scale / 2.0
        image = entity.image
        w, h = image.GetWidth(), image.GetHeight()
        w, h = int(w * bitmap_scale), int(h * bitmap_scale)
        image.Rescale(w, h, wx.IMAGE_QUALITY_HIGH)
        bitmap = wx.BitmapFromImage(image)
        if selected:
            x, y = w / 2, h / 2
            radius = entity.radius * scale
            dc = wx.MemoryDC(bitmap)
            dc = wx.GCDC(dc)
            dc.SetPen(wx.Pen(wx.Color(255, 0, 0), 1))
            dc.SetBrush(wx.Brush(wx.Color(255, 0, 0, 128)))
            dc.DrawCircle(x, y, radius)
        return bitmap
        
class Control(wx.Panel):
    clipboard = set()
    cache = BitmapCache()
    def __init__(self, parent):
        super(Control, self).__init__(parent, -1, style=wx.WANTS_CHARS)
        self._draw_params = None # (scale, (width, height))
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
    @property
    def draw_params(self):
        return self._draw_params or (self.scale, self.GetClientSize())
    def on_size(self, event):
        event.Skip()
        self.Refresh()
    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
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
        s, (w, h) = self.draw_params
        l, b, r, t = self.level.bounds
        p = (w - (r - l) * s) / 2
        x = l + (x - p) / s
        p = (h - (t - b) * s) / 2
        y = t - (y - p) / s
        return x, y
    def cc2wx(self, x, y, radius=None):
        s, (w, h) = self.draw_params
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
            radius = radius * s
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
    def create_bitmap(self, scale=1, size=256):
        l, b, r, t = self.level.bounds
        w, h = r - l, t - b
        if size: # make square
            w, h = max(w, h), max(w, h)
        bitmap = wx.EmptyBitmap(w, h)
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.BLACK_BRUSH)
        dc.Clear()
        self._draw_params = (scale, (w, h))
        self.draw_level(dc)
        self._draw_params = None
        del dc
        if size: # scale to size
            image = wx.ImageFromBitmap(bitmap)
            try:
                image = wx2pil(image)
                image = image.resize((size, size), Image.ANTIALIAS)
                image = pil2wx(image)
            except Exception:
                image.Rescale(size, size, wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.BitmapFromImage(image)
        return bitmap
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
        keys = set()
        for entity in self.level.entities:
            key = entity.draw_path_key
            if key is None or key not in keys:
                self.draw_path(dc, entity)
                if key:
                    keys.add(key)
        for entity in self.level.entities:
            self.draw_entity(dc, entity)
    def draw_path(self, dc, entity):
        path = entity.path
        dc.SetPen(wx.Pen(wx.WHITE, 1, wx.DOT))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        if isinstance(path, CircularPath):
            dx = entity.x - path.x
            dy = entity.y - path.y
            radius = (dx * dx + dy * dy) ** 0.5
            self.circle(dc, path.x, path.y, radius)
        elif isinstance(path, LinearPath):
            dx = entity.x - path.x
            dy = entity.y - path.y
            self.line(dc, entity.x, entity.y, entity.x - dx * 2, entity.y - dy * 2)
    def draw_entity(self, dc, entity):
        scale, dummy = self.draw_params
        selected = entity in self.selection
        bitmap = Control.cache.get_bitmap(entity, scale, selected)
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
    def select_all(self, cls=None):
        entities = set()
        for entity in self.level.entities:
            if cls and not isinstance(entity, cls):
                continue
            entities.add(entity)
        self.selection = entities
        self.Refresh()
    def mirror(self, mx, my):
        for entity in self.selection:
            entity.x *= mx
            entity.y *= my
            if entity.path:
                entity.path.x *= mx
                entity.path.y *= my
        self.changed()
    def rotate(self, degrees):
        for entity in self.selection:
            entity.x, entity.y = self._rotate(entity.x, entity.y, degrees)
            if entity.path:
                entity.path.x, entity.path.y = self._rotate(entity.path.x, entity.path.y, degrees)
        self.changed()
    def _rotate(self, x, y, degrees):
        if x == 0 and y == 0:
            return x, y
        d = (x * x + y * y) ** 0.5
        angle = math.atan2(y, x)
        angle = angle + math.radians(degrees)
        x = math.cos(angle) * d
        y = math.sin(angle) * d
        return x, y
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
                other.x -= dx * i
                other.y -= dy * i
                if other.path:
                    other.path.x -= dx * i
                    other.path.y -= dy * i
                self.level.entities.append(other)
        self.changed()
    def circular_array(self, count):
        step = 360.0 / count
        for entity in self.selection:
            for i in range(1, count):
                degrees = step * i
                other = entity.copy()
                other.x, other.y = self._rotate(other.x, other.y, degrees)
                if other.path:
                    other.path.x, other.path.y = self._rotate(other.path.x, other.path.y, degrees)
                self.level.entities.append(other)
        self.changed()
    def delete_path(self):
        for entity in self.selection:
            entity.path = None
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
        if event.CmdDown():
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
            if not event.CmdDown():
                dx *= self.minor_grid[0]
                dy *= self.minor_grid[1]
            for entity in self.selection:
                entity.x += dx
                entity.y += dy
                if entity.path:
                    entity.path.x += dx
                    entity.path.y += dy
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
            if event.CmdDown():
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
                self.moving = [(e, e.x, e.y, e.path.copy() if e.path else None) for e in entities]
                self.CaptureMouse()
        else:
            if not event.CmdDown():
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
            if event.CmdDown():
                self.selection ^= entities
            else:
                self.selection = entities
        if self.moving:
            for entity, sx, sy, original_path in self.moving:
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
            entity, sx, sy, original_path = self.moving[0]
            mx = self.snap(sx + dx, self.minor_grid[0]) - sx
            my = self.snap(sy + dy, self.minor_grid[1]) - sy
            for entity, sx, sy, original_path in self.moving:
                entity.x = sx + mx
                entity.y = sy + my
                if entity.path and original_path:
                    entity.path.x = original_path.x + mx
                    entity.path.y = original_path.y + my
            self.Refresh()
        if self.selecting:
            self.Refresh()
            
# Main
def main():
    app = wx.PySimpleApp()
    frame = Frame()
    frame.Show()
    app.MainLoop()
    
if __name__ == '__main__':
    main()
    