rule Script_Powershell_Downloader
{
  meta:
    reason = "SCRIPT_DOWNLOADER"
    score = 95
    source = "yara"
  strings:
    $dl1 = "Invoke-WebRequest" nocase ascii wide
    $dl2 = "DownloadString" nocase ascii wide
    $dl3 = "Invoke-Expression" nocase ascii wide
    $dl4 = "IEX(New-Object Net.WebClient).DownloadString" ascii wide
    $url = /https?:\/\/[^\s"'<>]+/ nocase
  condition:
    normalized_type == "script" and (($url and 1 of ($dl*)) or 2 of ($dl*))
}

rule Script_Powershell_Encoded
{
  meta:
    reason = "SCRIPT_POWERSHELL_ENCODED"
    score = 85
    source = "yara"
  strings:
    $enc = /(^|[\s\"'])-enc([\s\"']|$)/ nocase
    $b64 = "FromBase64String" nocase ascii wide
  condition:
    normalized_type == "script" and any of them
}
