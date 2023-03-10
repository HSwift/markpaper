import argparse
from plugins import install_references_list

parser = argparse.ArgumentParser(description="Convert Markdown to DOCX or HTML with paper format.")
parser.add_argument("input_file", type=str, help="markdown file path for converting")
parser.add_argument("--output", type=str, default="", help="output filename")
parser.add_argument("--format", type=str, choices=["html", "docx"], default="html", help="output format")
parser.add_argument("--docx-base-file", type=str, default="default.docx", help="provide docx base style and framework")
args = parser.parse_args()


def output_file_name():
    if args.output == "":
        input_name: str = args.input_file
        if (pos := input_name.rfind(".")) != -1:
            input_name = input_name[:pos]
        else:
            input_name = input_name
        output_name = input_name + "." + args.format
    else:
        output_name = args.output
    return output_name


if args.format == "docx":
    from docxConvertor import DOCXConvertor

    docx = DOCXConvertor(args.docx_base_file)
    install_references_list(docx.md)
    data = open(args.input_file, encoding="utf-8").read()
    docx.read(data)
    docx.save(output_file_name())
elif args.format == "html":
    from htmlConvertor import HTMLConvertor

    html = HTMLConvertor()
    install_references_list(html.md)
    data = open(args.input_file, encoding="utf-8").read()
    html.read(data)
    html.save(output_file_name())
