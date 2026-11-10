param([string]$BrokerHost='127.0.0.1',[int]$Port=1883)
$ErrorActionPreference='Stop'
$client=[Net.Sockets.TcpClient]::new()
try {
    $task=$client.ConnectAsync($BrokerHost,$Port)
    if (!$task.Wait(2000) -or !$client.Connected) { throw 'Broker TCP check failed' }
    Write-Output 'Broker TCP reachable (not an MQTT protocol verification)'
} finally { $client.Dispose() }
