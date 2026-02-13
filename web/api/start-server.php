<?php
/**
 * PackAssist – Python Server Auto-Launcher
 * 
 * Called from the frontend on page load. Checks if mesh_server.py is running
 * and starts it in the background if not (Windows XAMPP environment).
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// Path to the project root (two levels up from web/api/)
$projectRoot = realpath(__DIR__ . '/../../');
$scriptPath  = $projectRoot . DIRECTORY_SEPARATOR . 'mesh_server.py';
$venvPython  = $projectRoot . DIRECTORY_SEPARATOR . 'env' . DIRECTORY_SEPARATOR . 'Scripts' . DIRECTORY_SEPARATOR . 'python.exe';
$systemPython = 'python'; // fallback

// Choose Python executable
$pythonExe = file_exists($venvPython) ? '"' . $venvPython . '"' : $systemPython;

// 1. Check if server is already running by probing the health endpoint
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
        'message' => 'mesh_server.py is already running on port 8787'
    ]);
    exit;
}

// 2. Not running — try to start it
if (!file_exists($scriptPath)) {
    http_response_code(404);
    echo json_encode([
        'status'  => 'error',
        'message' => 'mesh_server.py not found at: ' . $scriptPath
    ]);
    exit;
}

// Build command for Windows background execution
if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
    // Windows: use 'start /B' to run in background, redirect output to a log file
    $logFile = $projectRoot . DIRECTORY_SEPARATOR . 'mesh_server.log';
    $cmd = 'start /B "" ' . $pythonExe . ' "' . $scriptPath . '" > "' . $logFile . '" 2>&1';
    pclose(popen($cmd, 'r'));
} else {
    // Linux/Mac: nohup + background
    $cmd = $pythonExe . ' "' . $scriptPath . '" > /dev/null 2>&1 &';
    exec($cmd);
}

// 3. Wait a moment and verify it started
sleep(2);

$response = @file_get_contents($serverUrl, false, $ctx);
if ($response !== false) {
    $data = json_decode($response, true);
    if (isset($data['status']) && $data['status'] === 'ok') {
        echo json_encode([
            'status'    => 'started',
            'message'   => 'mesh_server.py started successfully',
            'pymeshlab' => $data['pymeshlab'] ?? false
        ]);
        exit;
    }
}

echo json_encode([
    'status'  => 'started_unverified',
    'message' => 'mesh_server.py launch command sent, but health check did not respond yet. It may need a few more seconds.'
]);
