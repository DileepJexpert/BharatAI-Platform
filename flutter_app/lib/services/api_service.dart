import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/platform_health.dart';

class ApiService extends ChangeNotifier {
  String _baseUrl = 'http://localhost:8000';
  String _apiKey = 'dev-asha-key-001';
  String _currentApp = 'asha_health';
  bool _isConnected = false;
  PlatformHealth? _health;

  // API key per app
  final Map<String, String> _appKeys = {
    'asha_health': 'dev-asha-key-001',
    'lawyer_ai': 'dev-lawyer-key-001',
  };

  String get baseUrl => _baseUrl;
  String get apiKey => _apiKey;
  String get currentApp => _currentApp;
  bool get isConnected => _isConnected;
  PlatformHealth? get health => _health;

  void setBaseUrl(String url) {
    _baseUrl = url.trimRight().replaceAll(RegExp(r'/+$'), '');
    notifyListeners();
  }

  void setCurrentApp(String appId) {
    _currentApp = appId;
    _apiKey = _appKeys[appId] ?? _apiKey;
    notifyListeners();
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'X-API-Key': _apiKey,
      };

  // --- Health Check ---
  Future<PlatformHealth?> checkHealth() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/health'))
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _health = PlatformHealth.fromJson(jsonDecode(response.body));
        _isConnected = true;
      } else {
        _isConnected = false;
      }
    } catch (e) {
      _isConnected = false;
      _health = null;
    }
    notifyListeners();
    return _health;
  }

  // --- Chat (text-only) ---
  Future<Map<String, dynamic>> chat(String text, String sessionId,
      {String? languageHint}) async {
    final body = {
      'text': text,
      'session_id': sessionId,
      if (languageHint != null) 'language_hint': languageHint,
    };

    final response = await http
        .post(
          Uri.parse('$_baseUrl/$_currentApp/chat'),
          headers: _headers,
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 60));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw ApiException(response.statusCode, response.body);
    }
  }

  // --- Session ---
  Future<Map<String, dynamic>?> getSession(String sessionId) async {
    try {
      final response = await http
          .get(
            Uri.parse('$_baseUrl/$_currentApp/session/$sessionId'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (_) {}
    return null;
  }

  Future<void> deleteSession(String sessionId) async {
    await http
        .delete(
          Uri.parse('$_baseUrl/$_currentApp/session/$sessionId'),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 10));
  }

  // --- Models ---
  Future<Map<String, dynamic>> getModels() async {
    final response = await http
        .get(Uri.parse('$_baseUrl/models'))
        .timeout(const Duration(seconds: 5));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw ApiException(response.statusCode, response.body);
  }

  // --- Admin: Load model ---
  Future<Map<String, dynamic>> loadModel(String modelKey) async {
    final response = await http
        .post(
          Uri.parse('$_baseUrl/admin/load-model'),
          headers: _headers,
          body: jsonEncode({'model_key': modelKey}),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw ApiException(response.statusCode, response.body);
  }

  // --- ASHA: List visits ---
  Future<Map<String, dynamic>> listVisits({String? workerId}) async {
    final uri = workerId != null
        ? '$_baseUrl/asha_health/visits?worker_id=$workerId'
        : '$_baseUrl/asha_health/visits';

    final response = await http
        .get(Uri.parse(uri), headers: _headers)
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw ApiException(response.statusCode, response.body);
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String body;

  ApiException(this.statusCode, this.body);

  @override
  String toString() => 'API Error $statusCode: $body';
}
