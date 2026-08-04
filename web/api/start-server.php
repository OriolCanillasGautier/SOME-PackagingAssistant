<?php
/**
 * PackAssist – Python Server Auto-Launcher
 * 
 * Called from the frontend on page load. Checks if server.py is running
 * and starts it in the background if not.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$projectRoot = realpath(__DIR__ . '/../../');
$scriptPath  = $projectRoot . DIRECTORY_SEPARATOR . 'server.py';
$venvPython  = $projectRoot . DIRECTORY_SEPARATOR . 'env' . DIRECTORY_SEPARATOR . 'Scripts' . DIRECTORY_SEPARATOR . 'python.exe';
$systemPython = 'python3';

$pythonExe = file_exists($venvPython) ? '"' . $venvPython . '"' : $systemPython;

$serverUrl = 'http://127.0.0.1:8787/api/health';
$running   = false;

$ctx = stream_context_create([
    'http' => ['timeout' => 1.5, 'method' => 'GET']
]);

$response = @file_get_contents($serverUrl, false, $ctx);
if ($response !== false) {
    $data = json_decode($response, true);
    if (isset($data['status']) && $data['status'] === 'ok') {
        $running = true;
    }
}

if ($running) {
    echo json_encode([
        'status'  => 'already_running',
        'message' => 'server.py is already running on port 8787'
    ]);
    exit;
}

if (!file_exists($scriptPath)) {
    http_response_code(404);
    echo json_encode([
        'status'  => 'error',
        'message' => 'server.py not found at: ' . $scriptPath
    ]);
    exit;
}

if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
    $logFile = $projectRoot . DIRECTORY_SEPARATOR . 'server.log';
    $cmd = 'start /B "" ' . $pythonExe . ' "' . $scriptPath . '" > "' . $logFile . '" 2>&1';
    pclose(popen($cmd, 'r'));
} else {
    $cmd = $pythonExe . ' "' . $scriptPath . '" > /dev/null 2>&1 &';
    exec($cmd);
}

sleep(2);

$response = @file_get_contents($serverUrl, false, $ctx);
if ($response !== false) {
    $data = json_decode($response, true);
    if (isset($data['status']) && $data['status'] === 'ok') {
        echo json_encode([
            'status'    => 'started',
            'message'   => 'server.py started successfully',
            'pymeshlab' => $data['pymeshlab'] ?? false,
            'cuda'      => $data['cuda'] ?? false
        ]);
        exit;
    }
}

echo json_encode([
    'status'  => 'started_unverified',
    'message' => 'server.py launch command sent, but health check did not respond yet.'
]);
