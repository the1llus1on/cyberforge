param(
    [Parameter(Mandatory = $true)]
    [string] $Destination
)
$ErrorActionPreference = "Stop"
$Destination = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) {
    throw "The compiler destination already exists."
}
$download = Join-Path ([IO.Path]::GetTempPath()) ("cyberforge-inno-" + [Guid]::NewGuid() + ".exe")
try {
    $url = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe"
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $download
    $sign = Get-AuthenticodeSignature -LiteralPath $download
    if ($sign.Status -ne "Valid" -or $sign.SignerCertificate.Subject -notlike "*Pyrsys B.V.*") {
        throw "The pinned Inno Setup publisher signature could not be verified."
    }
    $install = Start-Process -FilePath $download -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/PORTABLE=1",
        ('/DIR="' + $Destination + '"')
    ) -Wait -PassThru
    if ($install.ExitCode -ne 0 -or !(Test-Path (Join-Path $Destination "ISCC.exe"))) {
        throw "Pinned Inno Setup installation failed."
    }
}
finally {
    if (Test-Path -LiteralPath $download) {
        Remove-Item -LiteralPath $download
    }
}
