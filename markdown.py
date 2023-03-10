from __future__ import annotations
import re
import yaml

from typing import Optional, Literal, Callable
from pydantic import BaseModel, Extra


class Component:
    markdown: Markdown
    parent: Markdown | Container
    args: dict[str, str | int] | None
    config: MarkdownConfig.Base | None

    def __init__(self, parent: Markdown | Container) -> None:
        self.parent = parent
        if isinstance(parent, Markdown):
            self.markdown = parent
        else:
            self.markdown = parent.markdown
        self.parent.append(self)
        self.config = None

    def get_parent_section(self) -> Section:
        cur = self
        while not isinstance(cur, Markdown):
            if isinstance(cur, Section):
                return cur
            cur = cur.parent
        raise Exception("can not find parent section")

    def set_macro(self, macro: Macro | None):
        if macro is not None and self.__class__.__name__.lower() == macro.type.lower():
            self.args = macro.consume()
        return self

    def get_config(self) -> MarkdownConfig.Base | None:
        def lower_first(s):
            return s[:1].lower() + s[1:] if s else ''

        if self.config != None:
            return self.config

        if hasattr(self.markdown.markdownConfig, lower_first(self.__class__.__name__)):
            return getattr(self.markdown.markdownConfig, lower_first(self.__class__.__name__))
        return None


class Container(Component):
    def __init__(self, parent: Markdown | Container) -> None:
        super().__init__(parent)
        self.components: list[Component] = []

    def append(self, component: Component):
        self.components.append(component)

    def __len__(self):
        return len(self.components)

    def __getitem__(self, key):
        return self.components[key]

    def __setitem__(self, key, value):
        self.components = value

    def find(self, callback: Callable[[Component], bool]):
        for c in self.components:
            if callback(c):
                return c
            if isinstance(c, Container):
                return c.find(callback)


class Section(Container):
    components: list[Component]
    level: int
    number: int
    parent: Markdown | Section
    title: Title

    def __init__(self, parent: Markdown | Section, level: int) -> None:
        self.level = level
        if isinstance(parent, Markdown):
            self.parent = parent
            self.number = 1
        else:
            self.parent = parent.get_parent(level)
            self.number = len(self.parent.get_sub_sections()) + 1
        super().__init__(self.parent)

    def get_parent(self, level):
        cur = self
        while level <= cur.level:
            cur = cur.parent
        return cur

    def get_parents(self) -> list[Section]:
        cur = self
        parents = []
        while cur.level != 0:
            parents.append(cur)
            cur = cur.parent
        return parents[::-1]

    def get_sub_sections(self) -> list[Component]:
        return list(filter(lambda x: isinstance(x, Section), self.components))

    def __str__(self) -> str:
        return f"<Section level={self.level} len={len(self)}>"

    def set_title(self, title):
        self.title = Title(self).parse(title)
        return self


class Title(Component):
    text: str
    parent: Section

    def parse(self, text: str):
        self.text = re.match(r"^#+ (.*)$", text).groups()[0]
        return self

    @property
    def level(self):
        return self.parent.level

    def __str__(self) -> str:
        return f"<Title text={self.text}>"

    def get_config(self):
        if hasattr(self.markdown.markdownConfig, f"h{self.parent.level}"):
            return getattr(self.markdown.markdownConfig, f"h{self.parent.level}")
        return None


class Image(Component):
    name: str
    link: str
    number: int

    def parse(self, image):
        r = re.match(r"!\[([^]]+)]\(([^)]+)\)", image).groups()
        self.name = r[0]
        self.link = r[1]
        self.markdown.image_dict[self.name] = self
        self.number = len(self.markdown.image_dict)
        return self

    def __str__(self) -> str:
        return f"<Image name={self.name} link={self.link}>"


class Code(Component):
    name: str
    code_lines: list[str]
    number: int

    def parse(self, code: list[str]):
        self.name = code[0][3:]
        if self.name == "":
            raise Exception("code name required")
        self.code_lines = code[1:]
        self.markdown.code_dict[self.name] = self
        self.number = len(self.markdown.code_dict)
        return self

    @property
    def code(self):
        config: MarkdownConfig.Code = self.get_config()
        if config.show_line_numbers:
            res = []
            for i in range(len(self.code_lines)):
                res.append(f"{i + 1} {self.code_lines[i]}")
            return '\n'.join(res)
        else:
            return '\n'.join(self.code_lines)

    def __str__(self) -> str:
        return f"<Code name={self.name}>"


class Paragraph(Container):
    def parse(self, text):
        self.components: list[Text | ImageRef | TableRef | Ref] = []
        syntax = r"(?P<escape>\\.)|" \
                 r"(?P<image_ref>@image\[\[.*?\]\])|" \
                 r"(?P<table_ref>@table\[\[.*?\]\])|" \
                 r"(?P<code_ref>@code\[\[.*?\]\])|" \
                 r"(?P<ref>@\[\[.*?\]\])|" \
                 r"(?P<italic>\*[^*]+\*)|" \
                 r"(?P<bold>\*\*[^*]+\*\*)|" \
                 r"(?P<code>`[^`]+`)"
        res = re.finditer(syntax, text)
        start = 0
        for g in res:
            if start != g.start():
                Text(self).parse(text[start:g.start()])
            start = g.end()
            match g.groupdict():
                case {"image_ref": t} if t is not None:
                    ImageRef(self).parse(t)
                case {"table_ref": t} if t is not None:
                    TableRef(self).parse(t)
                case {"code_ref": t} if t is not None:
                    CodeRef(self).parse(t)
                case {"ref": t} if t is not None:
                    Ref(self).parse(t)
                case {"italic": t} if t is not None:
                    ItalicSpan(self).parse(t)
                case {"bold": t} if t is not None:
                    BoldSpan(self).parse(t)
                case {"escape": t} if t is not None:
                    EscapeSpan(self).parse(t)
                case {"code": t} if t is not None:
                    CodeSpan(self).parse(t)
        if start != len(text):
            Text(self).parse(text[start:])
        return self

    def __str__(self) -> str:
        return "<Paragraph len={len(self)}>"


class Table(Container):
    components: list[TableRow | TableHead]
    name: str
    head: TableHead
    row_num: int
    col_num: int
    number: int

    def parse(self, table: list[str]):
        self.head = TableHead(self)
        self.head.parse(table[0])
        self.row_num = len(table) - 1
        self.col_num = len(self.head)
        for line in table[2:]:
            TableRow(self).parse(line)
        try:
            self.name = self.args['name']
        except (AttributeError, KeyError):
            raise Exception("table name required")
        self.markdown.table_dict[self.name] = self
        self.number = len(self.markdown.table_dict)
        return self

    def __str__(self) -> str:
        return f"<Table row={self.row_num} col={self.col_num}>"


class TableRow(Container):
    def parse(self, row: str):
        t = filter(lambda x: x != "", row.split("|"))
        for i in t:
            TableCell(self).parse(i.strip())
        return self

    def __str__(self) -> str:
        return "<TableRow>"


class TableHead(Container):
    def parse(self, row: str):
        t = filter(lambda x: x != "", row.split("|"))
        for i in t:
            TableHeadCell(self).parse(i.strip())
        return self

    def __str__(self) -> str:
        return "<TableHead>"


class TableCell(Paragraph):
    def parse(self, text):
        super().parse(text)
        return self

    def __str__(self) -> str:
        return "<TableCell>"


class TableHeadCell(Paragraph):
    def parse(self, text):
        super().parse(text)
        return self

    def __str__(self) -> str:
        return "<TableHeadCell>"


class Text(Component):
    text: str

    def parse(self, text):
        self.text = text
        return self

    def __str__(self) -> str:
        return self.text


class ImageRef(Component):
    name: str

    def parse(self, name):
        self.name = name[8:-2]
        return self

    def __str__(self) -> str:
        return f"<ImageRef name={self.name}>"


class TableRef(Component):
    name: str

    def parse(self, name):
        self.name = name[8:-2]
        return self

    def __str__(self) -> str:
        return f"<TableRef name={self.name}>"


class CodeRef(Component):
    name: str

    def parse(self, name):
        self.name = name[7:-2]
        return self

    def __str__(self) -> str:
        return f"<CodeRef ref={self.name}>"


class Ref(Component):
    ref: str
    number: int

    def parse(self, ref):
        self.ref = ref[3:-2]
        self.markdown.ref_list.append(self.ref)
        self.number = len(self.markdown.ref_list)
        return self

    def __str__(self) -> str:
        return f"<Ref ref={self.ref}>"


class ItalicSpan(Component):
    text: str

    def parse(self, text):
        self.text = text[1:-1]
        return self

    def __str__(self) -> str:
        return f"<ItalicSpan ref={self.text}>"


class BoldSpan(Component):
    text: str

    def parse(self, text):
        self.text = text[2:-2]
        return self

    def __str__(self) -> str:
        return f"<BoldSpan text={self.text}>"


class EscapeSpan(Text):
    text: str

    def parse(self, text):
        super().parse(text[1:])
        return self


class CodeSpan(Text):
    text: str

    def parse(self, text):
        self.text = text[1:-1]

    def __str__(self) -> str:
        return f"<CodeSpan text={self.text}>"


class Macro:
    type: str
    args: dict[str, str | int] | None
    consumed: bool

    def __init__(self, macro):
        s_type = r"""(?P<type>[a-zA-Z]+[a-zA-Z_-]*)"""
        s_k = r"""([a-zA-Z]+[a-zA-Z_-]*)"""
        s_v = r"""("(\\.|[^\\"])*"|'(\\.|[^\\'])*'|\d+)"""
        s_arg = f"(?P<arg>({s_k}={s_v})(,{s_k}={s_v})*)"
        s = f"@{s_type}(\\({s_arg}\\)|\\(\\))"
        r = re.match(f"^{s}$", macro)
        if r is None:
            raise Exception("macro not recognized")
        d = r.groupdict()
        self.type = d["type"]
        if "arg" in d:
            args = re.findall(f"({s_k}={s_v})", d["arg"])
            args = list(map(lambda x: x[0], args))
            self.args = {}
            for arg in args:
                g = re.match(f"{s_k}={s_v}", arg).groups()
                if g[1].isnumeric():
                    self.args[g[0]] = int(g[1])
                else:
                    self.args[g[0]] = g[1][1:-1].encode('raw_unicode_escape').decode('unicode_escape')
        else:
            self.args = None
        self.consumed = False

    def consume(self):
        if self.consumed:
            return None
        else:
            self.consumed = True
            return self.args


class Markdown:
    markdownConfig: MarkdownConfig
    document: Section
    markdown: Markdown
    parent: None
    image_dict: dict[str, Image]
    table_dict: dict[str, Table]
    ref_list: list[str]
    pre_parse_hooks: list[Callable[[Markdown], None]]
    post_parse_hooks: list[Callable[[Markdown], None]]

    def __init__(self):
        self.markdownConfig = MarkdownConfig.default()
        self.document = Section(self, 0)
        self.markdown = self
        self.parent = None
        self.image_dict = {}
        self.table_dict = {}
        self.code_dict = {}
        self.ref_list = []
        self.pre_parse_hooks = []
        self.post_parse_hooks = []

    def pre_parse_hook(self):
        for hook in self.pre_parse_hooks:
            hook(self)

    def post_parse_hook(self):
        for hook in self.post_parse_hooks:
            hook(self)

    def parse(self, text):
        self.pre_parse_hook()
        lines = text.split("\n")
        current_container = self.document
        yaml_content = table_content = code_content = []
        yaml_flag = table_flag = code_flag = False
        current_macro = None
        for line in lines:
            raw_line = line
            line = line.strip()
            if yaml_flag:
                if line == "---":
                    yaml_flag = False
                    self.markdownConfig = self.markdownConfig.read_from_yaml('\n'.join(yaml_content))
                else:
                    yaml_content.append(raw_line)
            elif code_flag:
                if line == "```":
                    code_flag = False
                    Code(current_container).set_macro(current_macro).parse(code_content)
                else:
                    code_content.append(raw_line)
            elif table_flag:
                if re.match(r"^\|.*\|$", line) is None:
                    table_flag = False
                    Table(current_container).set_macro(current_macro).parse(table_content)
                else:
                    table_content.append(line)
            elif line.startswith("# "):
                current_container = Section(current_container, 1).set_title(line).set_macro(current_macro)
            elif line.startswith("## "):
                current_container = Section(current_container, 2).set_title(line).set_macro(current_macro)
            elif line.startswith("### "):
                current_container = Section(current_container, 3).set_title(line).set_macro(current_macro)
            elif line.startswith("#### "):
                current_container = Section(current_container, 4).set_title(line).set_macro(current_macro)
            elif line.startswith("##### "):
                current_container = Section(current_container, 5).set_title(line).set_macro(current_macro)
            elif line.startswith("###### "):
                current_container = Section(current_container, 6).set_title(line).set_macro(current_macro)
            elif re.match(r"^!\[([^]]+)]\(([^)]+)\)$", line) is not None:
                Image(current_container).set_macro(current_macro).parse(line)
            elif re.match(r"^\|.*\|$", line) is not None:
                table_flag = True
                table_content = [line]
            elif line == "---" and len(yaml_content) == 0:
                yaml_flag = True
            elif line.startswith("```"):
                code_flag = True
                code_content = [line]
            elif re.match(r"^@[a-zA-Z]+[a-zA-Z_-]*\(.*\)$", line) is not None:
                current_macro = Macro(line)
            elif line == "":
                pass
            else:
                Paragraph(current_container).set_macro(current_macro).parse(line)
        self.post_parse_hook()

    def append(self, section: Section):
        self.document = section

    def find(self, callback: Callable[[Component], bool]):
        return self.document.find(callback)


class MarkdownConfig:
    class FontBase(BaseModel):
        color: Optional[str]
        font_size: Optional[int]
        en_font: Optional[str]
        cn_font: Optional[str]
        bold: Optional[bool]
        italic: Optional[bool]
        format: Optional[str]
        background: Optional[str]

        @property
        def docx_style_name(self):
            return ""

        @property
        def html_style_name(self):
            return ""

        @staticmethod
        def default() -> MarkdownConfig.FontBase:
            self = MarkdownConfig.FontBase()
            return self

        def merge(self):
            default_config: dict = self.__class__.default().dict(exclude_none=True)
            for k, v in default_config.items():
                if getattr(self, k) is None:
                    setattr(self, k, v)
            return self

    class Base(FontBase):
        width: Optional[int]
        height: Optional[int]
        first_line_indent: Optional[int]
        line_spacing: Optional[int]
        line_spacing_type: Optional[Literal["1", "1.5", "2"]]
        alignment: Optional[Literal["right", "left", "center", "justify"]]
        block_alignment: Optional[Literal["right", "left", "center"]]
        border_width: Optional[int]
        border_style: Optional[Literal["solid"]]
        border_color: Optional[str]
        border_collapse: Optional[Literal["collapse", "separate"]]
        word_wrap: Optional[bool]
        display: Optional[Literal["inline", "block", "none"]]
        margin: Optional[str]
        padding: Optional[str]

        @property
        def docx_style_name(self):
            return "Normal"

        @property
        def html_style_name(self):
            return "body"

        @staticmethod
        def default() -> MarkdownConfig.Base:
            self = MarkdownConfig.Base()
            self.font_size = 14
            self.en_font = "Times New Roman"
            self.cn_font = "宋体"
            self.bold = False
            self.italic = False
            self.alignment = "justify"
            self.first_line_indent = 0
            self.line_spacing_type = "1.5"
            self.margin = "25pt 25pt"
            self.padding = "0"
            return self

    class Heading(Base):
        format: Optional[str]

        @staticmethod
        def default() -> MarkdownConfig.Heading:
            self = MarkdownConfig.Heading()
            self.font_size = 20
            self.bold = True
            return self

        @property
        def docx_style_name(self):
            return "Heading"

        @property
        def html_style_name(self):
            return "h1,h2,h3,h4,h5,h6"

    class H1(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H1:
            self = MarkdownConfig.H1()
            self.font_size = 24
            self.bold = True
            self.alignment = "center"
            self.format = "{text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 1"

        @property
        def html_style_name(self):
            return ".head1"

    class H2(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H2:
            self = MarkdownConfig.H2()
            self.format = "{s1} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 2"

        @property
        def html_style_name(self):
            return ".head2"

    class H3(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H3:
            self = MarkdownConfig.H3()
            self.format = "{s1}.{s2} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 3"

        @property
        def html_style_name(self):
            return ".head3"

    class H4(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H4:
            self = MarkdownConfig.H4()
            self.format = "{s1}.{s2}.{s3} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 4"

        @property
        def html_style_name(self):
            return ".head4"

    class H5(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H5:
            self = MarkdownConfig.H5()
            self.format = "{s1}.{s2}.{s3}.{s4} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 5"

        @property
        def html_style_name(self):
            return ".head5"

    class H6(Heading):
        @staticmethod
        def default() -> MarkdownConfig.H6:
            self = MarkdownConfig.H6()
            self.format = "{s1}.{s2}.{s3}.{s4}.{s5} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Heading 6"

        @property
        def html_style_name(self):
            return ".head6"

    class Paragraph(Base):
        @staticmethod
        def default() -> MarkdownConfig.Paragraph:
            self = MarkdownConfig.Paragraph()
            self.first_line_indent = 2
            return self

        @property
        def docx_style_name(self):
            return "Paragraph"

        @property
        def html_style_name(self):
            return "p"

    class Image(Base):
        @staticmethod
        def default() -> MarkdownConfig.Image:
            self = MarkdownConfig.Image()
            self.block_alignment = "center"
            self.display = "block"
            self.format = "图{gi} {text}"
            return self

        @property
        def docx_style_name(self):
            return ""

        @property
        def html_style_name(self):
            return "img"

    class ImageRef(FontBase):
        @staticmethod
        def default() -> MarkdownConfig.ImageRef:
            self = MarkdownConfig.ImageRef()
            self.format = "图{gi}"
            return self

        @property
        def docx_style_name(self):
            return "Image Ref"

        @property
        def html_style_name(self):
            return ".image-ref"

    class ImageLabel(Base):
        @staticmethod
        def default() -> MarkdownConfig.ImageLabel:
            self = MarkdownConfig.ImageLabel()
            self.alignment = "center"
            return self

        @property
        def docx_style_name(self):
            return "Image Label"

        @property
        def html_style_name(self):
            return ".image-label"

    class Table(Base):
        @staticmethod
        def default() -> MarkdownConfig.Table:
            self = MarkdownConfig.Table()
            self.block_alignment = "center"
            self.border_width = 1
            self.border_style = "solid"
            self.border_color = "black"
            self.border_collapse = "collapse"
            self.format = "表{gi} {text}"
            return self

        @property
        def docx_style_name(self):
            return "Table Grid"

        @property
        def html_style_name(self):
            return "table"

    class TableLabel(Base):
        @staticmethod
        def default() -> MarkdownConfig.TableLabel:
            self = MarkdownConfig.TableLabel()
            self.alignment = "center"
            return self

        @property
        def docx_style_name(self):
            return "Table Label"

        @property
        def html_style_name(self):
            return ".table-label"

    class TableRef(FontBase):
        @staticmethod
        def default() -> MarkdownConfig.TableRef:
            self = MarkdownConfig.TableRef()
            self.format = "表{gi}"
            return self

        @property
        def docx_style_name(self):
            return "Table Ref"

        @property
        def html_style_name(self):
            return ".table-ref"

    class TableCell(Base):
        @staticmethod
        def default() -> MarkdownConfig.TableCell:
            self = MarkdownConfig.TableCell()
            self.border_width = 1
            self.border_style = "solid"
            self.border_color = "black"
            return self

        @property
        def docx_style_name(self):
            return "Table Cell"

        @property
        def html_style_name(self):
            return "td"

    class TableHeadCell(Base):
        @staticmethod
        def default() -> MarkdownConfig.TableHeadCell:
            self = MarkdownConfig.TableHeadCell()
            self.bold = True
            self.border_width = 1
            self.border_style = "solid"
            self.border_color = "black"
            return self

        @property
        def docx_style_name(self):
            return "Table Head Cell"

        @property
        def html_style_name(self):
            return "th"

    class Code(Base):
        show_line_numbers = False

        @staticmethod
        def default() -> MarkdownConfig.Code:
            self = MarkdownConfig.Code()
            self.border_width = 1
            self.border_style = "solid"
            self.border_color = "black"
            self.format = "代码{gi} {text}"
            return self

        @property
        def docx_style_name(self):
            return ""

        @property
        def html_style_name(self):
            return "pre"

    class CodeLabel(Base):
        @staticmethod
        def default() -> MarkdownConfig.CodeLabel:
            self = MarkdownConfig.CodeLabel()
            self.alignment = "center"
            return self

        @property
        def docx_style_name(self):
            return "Code Label"

        @property
        def html_style_name(self):
            return ".code-label"

    class CodeRef(FontBase):
        @staticmethod
        def default() -> MarkdownConfig.TableRef:
            self = MarkdownConfig.TableRef()
            self.format = "代码{gi}"
            return self

        @property
        def docx_style_name(self):
            return "Code Ref"

        @property
        def html_style_name(self):
            return ".code-ref"

    class All(Base):
        @staticmethod
        def default() -> MarkdownConfig.All:
            self = MarkdownConfig.All()
            self.margin = "0"
            self.padding = "0"
            return self

        @property
        def docx_style_name(self):
            return ""

        @property
        def html_style_name(self):
            return "*"

    class CodeSpan(FontBase):
        @staticmethod
        def default() -> MarkdownConfig.CodeSpan:
            self = MarkdownConfig.CodeSpan()
            self.background = "#e3e6e8"
            return self

        @property
        def docx_style_name(self):
            return "Code Span"

        @property
        def html_style_name(self):
            return "code"

    base: MarkdownConfig.Base = Base()
    heading: MarkdownConfig.Heading = Heading()
    h1: MarkdownConfig.H1 = H1()
    h2: MarkdownConfig.H2 = H2()
    h3: MarkdownConfig.H3 = H3()
    h4: MarkdownConfig.H4 = H4()
    h5: MarkdownConfig.H5 = H5()
    h6: MarkdownConfig.H6 = H6()
    paragraph: MarkdownConfig.Paragraph = Paragraph()
    image: MarkdownConfig.Image = Image()
    imageRef: MarkdownConfig.ImageRef = ImageRef()
    imageLabel: MarkdownConfig.ImageLabel = ImageLabel()
    table: MarkdownConfig.Table = Table()
    tableRef: MarkdownConfig.TableRef = TableRef()
    tableLabel: MarkdownConfig.TableLabel = TableLabel()
    tableCell: MarkdownConfig.TableCell = TableCell()
    tableHeadCell: MarkdownConfig.TableHeadCell = TableHeadCell()
    code: MarkdownConfig.Code = Code()
    codeLabel: MarkdownConfig.CodeLabel = CodeLabel()
    codeRef: MarkdownConfig.CodeRef = CodeRef()
    all: MarkdownConfig.All = All()
    codeSpan: MarkdownConfig.CodeSpan = CodeSpan()

    def list(self) -> list[str]:
        return list(self.__annotations__)

    def register_config(self, config_cls):
        name = config_cls.__name__
        name = name[0].lower() + name[1:]
        self.__annotations__[name] = config_cls.__name__
        setattr(self, name, config_cls())

    def items(self):
        items: dict[str, MarkdownConfig.Base] = {}
        for i in self.list():
            items[i] = getattr(self, i)
        return items.items()

    def merge(self):
        for e in self.list():
            getattr(self, e).merge()
        return self

    def read_from_yaml(self, y) -> MarkdownConfig:
        y = yaml.safe_load(y)
        props = self.list()
        if not isinstance(y, dict):
            raise Exception("yaml must be dict")
        for k, v in y.items():
            if k in props:
                setattr(self, k, getattr(self, k).parse_obj(v).merge())
        return self

    def dict(self):
        res = {}
        for i in self.items():
            res[i[0]] = i[1].dict(exclude_none=True)
        return res

    @staticmethod
    def default():
        self = MarkdownConfig()
        self.merge()
        return self
