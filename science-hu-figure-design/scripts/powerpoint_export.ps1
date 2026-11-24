param(
    [Parameter(Mandatory=$true)][string]$InputDeck,
    [Parameter(Mandatory=$true)][string]$OutputPdf
)

$ErrorActionPreference = "Stop"
$app = New-Object -ComObject PowerPoint.Application
$presentation = $null
try {
    $presentation = $app.Presentations.Open($InputDeck, -1, 0, 0)
    $presentation.SaveAs($OutputPdf, 32)
    Write-Output $app.Version
} finally {
    if ($null -ne $presentation) {
        $presentation.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
    }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
