import markdown

from markdown import MarkdownConfig
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element
from plugins import install_references_list
from utils import gen_placeholder


class HTMLConvertor:
    html: Element
    head: Element
    body: Element
    md: markdown.Markdown

    def __init__(self):
        self.html = Element('html')
        self.head = Element('head')
        self.body = Element('body')
        self.md = markdown.Markdown()

    def read(self, doc):
        self.md.parse(doc)
        self.set_styles(self.md.markdownConfig, self.head)
        self.html.append(self.head)
        self.gen(self.md.document, self.body)
        self.html.append(self.body)

    def save(self, file):
        ET.ElementTree(self.html).write(file, encoding='unicode', method='html')

    def gen(self, c: markdown.Component, p: Element):
        getattr(self, c.__class__.__name__)(c, p)

    def set_styles(self, o: MarkdownConfig, p: Element):
        style_dict: dict[str, dict[str, str]] = {}
        for _, v in o.items():
            if v.html_style_name != "":
                style_dict[v.html_style_name] = self.set_style_rule(v)

        style_text = ""
        for name, v in style_dict.items():
            style_text += f"{name} {{\n"
            for style_name, style_value in v.items():
                style_text += f"{style_name}: {style_value};\n"
            style_text += "}\n"
        style = Element('style')
        style.text = style_text
        p.append(style)

    def set_style_rule(self, o: MarkdownConfig.Base):
        d = o.dict(exclude_none=True)
        html_style = {}
        if "en_font" in d or "cn_font" in d:
            html_style['font-family'] = f'"{d.get("en_font", "")}", "{d.get("cn_font", "")}"'
        for item in d.items():
            match item:
                case ['width', width]:
                    html_style['width'] = f'{width}pt'
                case ['height', height]:
                    html_style['height'] = f'{height}pt'
                case ['color', color]:
                    html_style['color'] = color
                case ['font_size', size]:
                    html_style['font-size'] = f'{size}pt'
                case ['bold', True]:
                    html_style['font-weight'] = 'bold'
                case ['bold', False]:
                    html_style['font-weight'] = 'normal'
                case ['italic', True]:
                    html_style['font-style'] = 'italic'
                case ['italic', False]:
                    html_style['font-weight'] = 'normal'
                case ['first_line_indent', indent]:
                    html_style['text-indent'] = f'{indent}em'
                case ['line_spacing', spacing]:
                    html_style['line-height'] = f'{spacing}pt'
                case ['line_spacing_type', spacing]:
                    html_style['line-height'] = spacing
                case ['alignment', alignment]:
                    html_style['text-align'] = alignment
                case ['block_alignment', 'center']:
                    html_style['margin'] = '0 auto'
                case ['block_alignment', 'right']:
                    html_style['margin-left'] = 'auto'
                case ['block_alignment', 'left']:
                    html_style['margin-right'] = 'auto'
                case ['border_width', width]:
                    html_style['border-width'] = f'{width}pt'
                case ['border_style', style]:
                    html_style['border-style'] = style
                case ['border_color', color]:
                    html_style['border-color'] = color
                case ['border_collapse', collapse]:
                    html_style['border-collapse'] = collapse
                case ['display', display]:
                    html_style['display'] = display
                case ['margin', margin]:
                    html_style['margin'] = margin
                case ['padding', padding]:
                    html_style['padding'] = padding
        return html_style

    def Section(self, o: markdown.Section, p: Element):
        section = Element('div')
        p.append(section)
        for c in o.components:
            self.gen(c, section)

    def Title(self, o: markdown.Title, p: Element):
        title = Element(f'h{o.level}', attrib={'class': f'head{o.level}'})
        placeholders = gen_placeholder(o)
        title.text = o.get_config().format.format(**placeholders)
        p.append(title)

    def Image(self, o: markdown.Image, p: Element):
        image = Element('img', attrib={'src': o.link})
        p.append(image)
        image_name = Element('div', attrib={'class': 'image-label'})
        placeholders = gen_placeholder(o)
        image_name.text = o.get_config().format.format(**placeholders)
        p.append(image_name)

    def Paragraph(self, o: markdown.Paragraph, p: Element):
        paragraph = Element('p')
        for c in o.components:
            self.gen(c, paragraph)
        p.append(paragraph)

    def Table(self, o: markdown.Table, p: Element):
        table_name = Element('div', attrib={'class': 'table-label'})
        placeholders = gen_placeholder(o)
        table_name.text = o.get_config().format.format(**placeholders)
        p.append(table_name)
        table = Element('table')
        p.append(table)
        for c in o.components:
            self.gen(c, table)

    def TableRow(self, o: markdown.TableRow, p: Element):
        tr = Element('tr')
        p.append(tr)
        for c in o.components:
            self.gen(c, tr)

    def TableHead(self, o: markdown.TableHead, p: Element):
        tr = Element('tr')
        p.append(tr)
        for c in o.components:
            self.gen(c, tr)

    def TableCell(self, o: markdown.TableCell, p: Element):
        td = Element('td')
        p.append(td)
        for c in o.components:
            self.gen(c, td)

    def TableHeadCell(self, o: markdown.TableHeadCell, p: Element):
        th = Element('th')
        p.append(th)
        for c in o.components:
            self.gen(c, th)

    def Text(self, o: markdown.Text, p: Element):
        span = Element('span')
        span.text = o.text
        p.append(span)

    def ImageRef(self, o: markdown.ImageRef, p: Element):
        image = o.markdown.image_dict[o.name]
        span = Element('span', attrib={'class': 'image-ref'})
        placeholders = gen_placeholder(image)
        span.text = o.get_config().format.format(**placeholders)
        p.append(span)

    def TableRef(self, o: markdown.TableRef, p: Element):
        table = o.markdown.table_dict[o.name]
        span = Element('span', attrib={'class': 'table-ref'})
        placeholders = gen_placeholder(table)
        span.text = o.get_config().format.format(**placeholders)
        p.append(span)

    def CodeRef(self, o: markdown.CodeRef, p: Element):
        code = o.markdown.code_dict[o.name]
        placeholders = gen_placeholder(code)
        span = Element('span', attrib={'class': 'code-ref'})
        span.text = o.get_config().format.format(**placeholders)
        p.append(span)

    def Ref(self, o: markdown.Ref, p: Element):
        span = Element('sup')
        span.text = str(o.number)
        p.append(span)

    def ItalicSpan(self, o: markdown.ItalicSpan, p: Element):
        span = Element('i')
        span.text = o.text
        p.append(span)

    def BoldSpan(self, o: markdown.BoldSpan, p: Element):
        span = Element('b')
        span.text = o.text
        p.append(span)

    def EscapeSpan(self, o: markdown.EscapeSpan, p: Element):
        span = Element('span')
        span.text = o.text
        p.append(span)

    def Code(self, o: markdown.Code, p: Element):
        pre = Element('pre')
        pre.text = o.code
        code_name = Element('div', attrib={'class': 'code-label'})
        placeholders = gen_placeholder(o)
        code_name.text = o.get_config().format.format(**placeholders)
        p.append(pre)
        p.append(code_name)
