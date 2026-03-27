import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(
      text: context.read<ApiService>().baseUrl,
    );
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = context.watch<ApiService>();

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // --- Server URL ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Server URL',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      hintText: 'http://localhost:8000',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.link),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      ElevatedButton.icon(
                        onPressed: () {
                          api.setBaseUrl(_urlController.text);
                          api.checkHealth();
                        },
                        icon: const Icon(Icons.save, size: 18),
                        label: const Text('Save & Connect'),
                      ),
                      const SizedBox(width: 8),
                      Icon(
                        Icons.circle,
                        size: 12,
                        color: api.isConnected ? Colors.green : Colors.red,
                      ),
                      const SizedBox(width: 4),
                      Text(api.isConnected ? 'Connected' : 'Disconnected'),
                    ],
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // --- Quick URLs ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Quick Connect',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  _QuickUrlTile(
                    label: 'Local (same machine)',
                    url: 'http://localhost:8000',
                    onTap: (url) {
                      _urlController.text = url;
                      api.setBaseUrl(url);
                      api.checkHealth();
                    },
                  ),
                  _QuickUrlTile(
                    label: 'Local network (phone testing)',
                    url: 'http://192.168.1.X:8000',
                    onTap: (url) {
                      _urlController.text = url;
                    },
                  ),
                  _QuickUrlTile(
                    label: 'ngrok (WhatsApp testing)',
                    url: 'https://your-id.ngrok-free.app',
                    onTap: (url) {
                      _urlController.text = url;
                    },
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // --- Current App ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Active App',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                        value: 'asha_health',
                        label: Text('ASHA Health'),
                        icon: Icon(Icons.local_hospital),
                      ),
                      ButtonSegment(
                        value: 'lawyer_ai',
                        label: Text('Lawyer AI'),
                        icon: Icon(Icons.gavel),
                      ),
                    ],
                    selected: {api.currentApp},
                    onSelectionChanged: (selected) {
                      api.setCurrentApp(selected.first);
                    },
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // --- API Keys info ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('API Keys (MVP)',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  _KeyRow('ASHA Health', 'dev-asha-key-001'),
                  _KeyRow('Lawyer AI', 'dev-lawyer-key-001'),
                  const SizedBox(height: 8),
                  Text(
                    'Keys are auto-selected when you switch apps.',
                    style: TextStyle(
                        fontSize: 12, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // --- About ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('About',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  const Text('BharatAI Platform v1.0.0-mvp'),
                  const Text('Flutter Test Client & Admin Dashboard'),
                  const SizedBox(height: 4),
                  Text(
                    'Shared AI backend for Indian-language applications',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickUrlTile extends StatelessWidget {
  final String label;
  final String url;
  final ValueChanged<String> onTap;

  const _QuickUrlTile({
    required this.label,
    required this.url,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text(label, style: const TextStyle(fontSize: 13)),
      subtitle: Text(url, style: const TextStyle(fontSize: 12)),
      trailing: IconButton(
        icon: const Icon(Icons.content_copy, size: 18),
        onPressed: () => onTap(url),
      ),
    );
  }
}

class _KeyRow extends StatelessWidget {
  final String app;
  final String key;
  const _KeyRow(this.app, this.key);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 100,
            child: Text(app, style: const TextStyle(fontSize: 13)),
          ),
          Text(key,
              style: TextStyle(
                  fontSize: 12,
                  fontFamily: 'monospace',
                  color: Colors.grey.shade600)),
        ],
      ),
    );
  }
}
