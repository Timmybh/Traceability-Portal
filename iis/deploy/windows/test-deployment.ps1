[CmdletBinding()]
param(
    [int]$Port = 8374,
    [string]$Rfid = "(01)03608393748683(21)000000092192"
)

$ErrorActionPreference = "Stop"
$encodedRfid = [Uri]::EscapeDataString($Rfid)
$health = Invoke-RestMethod "http://127.0.0.1:$Port/health"
$data = Invoke-RestMethod "http://127.0.0.1:$Port/api/traceability?rfid=$encodedRfid"
$images = Invoke-RestMethod "http://127.0.0.1:$Port/api/traceability/images?rfid=$encodedRfid"

[pscustomobject]@{
    Health = $health.status
    Database = $health.database
    RFID = $data.RFID
    Customer = $data.TenNgan
    PO = $data.PO
    ProductCode = $data.ProductCode
    FrontImage = $images.front
    BackImage = $images.back
}
