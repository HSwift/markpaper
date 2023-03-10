from __future__ import annotations
from markdown import *


def install_references_list(markdown: Markdown):
    class ReferencesList(MarkdownConfig.Base):
        title: str = "参考文献"
        format: str = "[{id}] {text}"

        @staticmethod
        def default() -> ReferencesList:
            self = ReferencesList()
            self.word_wrap = True
            return self

        @property
        def docx_style_name(self):
            return "References List"

        @property
        def html_style_name(self):
            return ".references"

    def pre_hook(markdown: Markdown):
        markdown.markdownConfig.register_config(ReferencesList)

    def post_hook(markdown: Markdown):
        def find_level(x: Component):
            if isinstance(x, Section) and x.level == 1:
                return True

        section = Section(markdown.find(find_level), 2)
        config: ReferencesList = markdown.markdownConfig.referencesList
        Title(section).text = config.title
        format = config.format
        for id in range(len(markdown.ref_list)):
            text = markdown.ref_list[id]
            paragraph = Paragraph(section)
            paragraph.parse(format.format(id=id + 1, text=text))

    markdown.pre_parse_hooks.append(pre_hook)
    markdown.post_parse_hooks.append(post_hook)
