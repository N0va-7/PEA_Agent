rule Pdf_Embedded_JavaScript
{
  meta:
    reason = "PDF_EMBEDDED_JS"
    score = 88
    source = "yara"
  strings:
    $js1 = "/JavaScript" ascii
    $js2 = "/JS" ascii
  condition:
    normalized_type == "pdf" and any of them
}

rule Pdf_Launch_Action
{
  meta:
    reason = "PDF_LAUNCH_ACTION"
    score = 95
    source = "yara"
  strings:
    $launch = "/Launch" ascii
    $open_action = "/OpenAction" ascii
  condition:
    normalized_type == "pdf" and any of them
}
