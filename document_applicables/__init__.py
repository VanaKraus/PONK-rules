from pydantic import BaseModel
from typing import Type
from udapi.core.node import Node


class Documentable(BaseModel):
    class Config:
        # this is black magick
        @staticmethod
        def json_schema_extra(schema: dict, _):
            props = {}
            for k, v in schema.get('properties', {}).items():
                if not v.get("hidden", False):
                    props[k] = v
            schema["properties"] = props

    @classmethod
    def get_final_children(cls) -> list[Type['Documentable']]:
        children = cls.__subclasses__()
        final_children = []
        for child in children:
            if child.__subclasses__():
                children += child.__subclasses__()
            else:
                final_children.append(child)
        print([child.__name__ for child in final_children])
        return final_children

    def annotate_node(self, key: str, annotation, *node: Node):
        for nd in node:
            nd.misc[key] = annotation

    def get_node_annotation(self, key: str, node: Node):
        return node.misc.get(key)

    @classmethod
    def generate_doc_html(cls):
        html = f'<h1>{cls.__name__}</h1>'
        html += f'<button id={cls.__name__}-button>Show</button>'
        html += f'<div id={cls.__name__} style="display:none">'
        for child in cls.get_final_children():
            html += f'<h2>{child.__name__}</h2>'
            html += f'<button id={child.__name__}-button>Show</button>'

            docstring = child.__doc__
            attrs = None
            if 'Attributes:' in docstring:
                import re
                split_docstring = docstring.split('Attributes:')
                docstring = split_docstring[0]
                attrs = split_docstring[1].splitlines()
                attrs = [re.sub(r'  +', ' ', attr).strip() for attr in attrs]
                attrs = [attr for attr in attrs if attr != '']
                attrs = [re.sub(r' \([^)]+\): ', ':', attr).split(':') for attr in attrs]
                attrs = {attr[0]: attr[1] for attr in attrs}

            html += (f'<div id={child.__name__} style="display:none">'
                     f'{docstring.replace(chr(10), "<br>").replace("    ", "")}'
                     )
            html += f'<h4>Parameters</h4>'
            html += f'<button id={child.__name__}-params-button>Show</button>'
            html += f'<ul id={child.__name__}-params style="display:none">'
            for param in child.model_fields.items():
                name = param[0]
                field_info = param[1]
                if field_info.json_schema_extra and field_info.json_schema_extra.get('hidden'):
                    continue
                html += (f'<li><b>{name}</b>: '
                         f'{field_info.annotation.__name__} '
                         f'{" = " + str(field_info.default) if field_info.default is not None else ""} '
                         f'{"<i>" + field_info.description + "</i>" if field_info.description else ""}'
                         f'{"<i>" + attrs[name] + "</i>" if attrs and attrs.get(name) is not None else ""}'
                         f'</li>')
            html += '</ul>'
            html += '</div>'

        html += '</div>'
        return html

    @staticmethod
    def generate_doc_footer():
        return """<script>
        var buttons = document.getElementsByTagName('button');
        for (i = 0; i < buttons.length; i++) {
          buttons[i].addEventListener("click", function() {
            var id = this.id.replace('-button', '');
            var content = document.getElementById(id);
            if (content.style.display === "block") {
              content.style.display = "none";
              this.innerHTML = 'Show';
            } else {
              content.style.display = "block";
              this.innerHTML = 'Hide';
            }
          });
        }
        </script>
        """


MINIMAL_CONLLU = """# newdoc
# newpar
# sent_id = 1
# text = Tohle je test.
1	Tohle	tenhle	DET	PDNS1----------	Case=Nom|Gender=Neut|Number=Sing|PronType=Dem	3	nsubj	_	TokenRange=0:5
2	je	být	AUX	VB-S---3P-AAI--	Aspect=Imp|Mood=Ind|Number=Sing|Person=3|Polarity=Pos|Tense=Pres|VerbForm=Fin|Voice=Act	3	cop	_	TokenRange=6:8
3	test	test	NOUN	NNIS1-----A----	Animacy=Inan|Case=Nom|Gender=Masc|Number=Sing|Polarity=Pos	0	root	_	SpaceAfter=No|TokenRange=9:13
4	.	.	PUNCT	Z:-------------	_	3	punct	_	SpaceAfter=No|TokenRange=13:14"""
