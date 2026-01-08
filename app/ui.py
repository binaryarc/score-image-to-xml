from .ui_components import (
    badges_html,
    form_html,
    header_html,
    info_html,
    new_feature_html,
    script_block,
    status_html,
    style_block,
)


def upload_form_html() -> str:
    return f"""
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>악보 이미지 → MusicXML 변환기 v3.1</title>
        {style_block()}
      </head>
      <body>
        <div class="container">
          {header_html()}
          {badges_html()}
          {new_feature_html()}
          {form_html()}
          {status_html()}
          {info_html()}
        </div>
        {script_block()}
      </body>
    </html>
    """
