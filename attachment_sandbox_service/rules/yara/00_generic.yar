rule Eicar_Test_File
{
  meta:
    reason = "KNOWN_MALWARE_SIGNATURE"
    score = 100
    source = "yara"
  strings:
    $eicar = "X5O!P%@AP[4\\\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
  condition:
    $eicar
}

rule Credential_Phish_Url
{
  meta:
    reason = "IOC_SUSPICIOUS_URL"
    score = 50
    source = "yara"
  strings:
    $url = /https?:\/\/[^\s"'<>]+\/(login|signin|verify|update)/ nocase
  condition:
    (normalized_type == "pdf" or normalized_type == "script" or normalized_type == "office" or normalized_type == "text")
    and $url
}
