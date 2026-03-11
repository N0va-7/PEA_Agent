rule Lnk_Command_Chain
{
  meta:
    reason = "LNK_COMMAND_CHAIN"
    score = 95
    source = "yara"
  strings:
    $ps = "powershell.exe" nocase ascii wide
    $cmd = "cmd.exe" nocase ascii wide
    $wscript = "wscript.exe" nocase ascii wide
    $mshta = "mshta.exe" nocase ascii wide
  condition:
    normalized_type == "lnk" and any of them
}

rule Executable_Suspicious_Command
{
  meta:
    reason = "EXECUTABLE_SUSPICIOUS_IMPORT"
    score = 82
    source = "yara"
  strings:
    $ps = "powershell" nocase ascii wide
    $cmd = "cmd.exe" nocase ascii wide
    $urlmon = "urlmon" nocase ascii wide
    $shell = "shell32.dll" nocase ascii wide
  condition:
    normalized_type == "executable" and any of them
}
