<?php
/**
 * PackAssist Web - Simple Development Server
 * Run with: php -S localhost:8080 server.php
 */

$uri = urldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));

// Handle CORS for development
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Serve static files
$path = __DIR__ . $uri;

// Default to index.html
if ($uri === '/' || $uri === '') {
    $path = __DIR__ . '/index.html';
}

// Check if file exists
if (file_exists($path) && is_file($path)) {
    // Get MIME type
    $mimeTypes = [
        'html' => 'text/html',
        'css' => 'text/css',
        'js' => 'application/javascript',
        'json' => 'application/json',
        'png' => 'image/png',
        'jpg' => 'image/jpeg',
        'gif' => 'image/gif',
        'svg' => 'image/svg+xml',
        'woff' => 'font/woff',
        'woff2' => 'font/woff2',
        'stl' => 'application/octet-stream',
    ];
    
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    $mime = $mimeTypes[$ext] ?? 'application/octet-stream';
    
    header('Content-Type: ' . $mime);
    readfile($path);
    exit;
}

// 404 for non-existent files
http_response_code(404);
echo '404 Not Found';
