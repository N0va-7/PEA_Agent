rule Office_VBA_Macro
{
  meta:
    reason = "OFFICE_VBA_MACRO"
    score = 80
    source = "yara"
  strings:
    $vba = "vbaProject.bin" ascii wide
  condition:
    normalized_type == "office" and $vba
}

rule Office_Autoexec_Macro
{
  meta:
    reason = "OFFICE_AUTOEXEC_MACRO"
    score = 92
    source = "yara"
  strings:
    $autoopen = "AutoOpen" ascii wide
    $docopen = "Document_Open" ascii wide
    $wbopen = "Workbook_Open" ascii wide
  condition:
    normalized_type == "office" and any of them
}

rule Office_External_Link
{
  meta:
    reason = "OFFICE_EXTERNAL_LINK"
    score = 70
    source = "yara"
  strings:
    $template = "attachedTemplate" ascii wide
    $external = "TargetMode=\"External\"" ascii wide
  condition:
    normalized_type == "office" and any of them
}
