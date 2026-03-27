import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/chat_message.dart';
import '../services/api_service.dart';
import '../widgets/message_bubble.dart';
import '../widgets/domain_data_card.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _messages = <ChatMessage>[];
  String _sessionId = 'flutter-${DateTime.now().millisecondsSinceEpoch}';
  bool _isLoading = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    _controller.clear();

    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
      _isLoading = true;
    });
    _scrollToBottom();

    try {
      final api = context.read<ApiService>();
      final response = await api.chat(text, _sessionId);

      setState(() {
        _messages.add(ChatMessage(
          text: response['response_text'] ?? 'No response',
          isUser: false,
          domainData: response['domain_data'] as Map<String, dynamic>?,
          confidence: (response['confidence'] as num?)?.toDouble(),
          processingMs: response['processing_ms'] as int?,
          error: response['error'] as String?,
        ));
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _messages.add(ChatMessage(
          text: 'Error: $e',
          isUser: false,
          error: e.toString(),
        ));
        _isLoading = false;
      });
    }
    _scrollToBottom();
  }

  void _clearChat() {
    final api = context.read<ApiService>();
    api.deleteSession(_sessionId);
    setState(() {
      _messages.clear();
      _sessionId = 'flutter-${DateTime.now().millisecondsSinceEpoch}';
    });
  }

  @override
  Widget build(BuildContext context) {
    final api = context.watch<ApiService>();
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Text('BharatAI'),
            const SizedBox(width: 8),
            _AppChip(appId: api.currentApp),
          ],
        ),
        actions: [
          // Connection indicator
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Icon(
              Icons.circle,
              size: 12,
              color: api.isConnected ? Colors.green : Colors.red,
            ),
          ),
          // App selector
          PopupMenuButton<String>(
            icon: const Icon(Icons.apps),
            tooltip: 'Switch App',
            onSelected: (appId) => api.setCurrentApp(appId),
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'asha_health',
                child: ListTile(
                  leading: Icon(Icons.local_hospital, color: Colors.red),
                  title: Text('ASHA Health'),
                  subtitle: Text('Patient visit recording'),
                ),
              ),
              const PopupMenuItem(
                value: 'lawyer_ai',
                child: ListTile(
                  leading: Icon(Icons.gavel, color: Colors.indigo),
                  title: Text('Lawyer AI'),
                  subtitle: Text('Legal assistance'),
                ),
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear chat',
            onPressed: _clearChat,
          ),
        ],
      ),
      body: Column(
        children: [
          // Connection banner
          if (!api.isConnected)
            MaterialBanner(
              content: Text(
                'Not connected to ${api.baseUrl}',
                style: const TextStyle(color: Colors.white),
              ),
              backgroundColor: Colors.red.shade700,
              actions: [
                TextButton(
                  onPressed: () => api.checkHealth(),
                  child: const Text('RETRY',
                      style: TextStyle(color: Colors.white)),
                ),
              ],
            ),

          // Messages
          Expanded(
            child: _messages.isEmpty
                ? _EmptyState(appId: api.currentApp)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (_, index) {
                      final msg = _messages[index];
                      return Column(
                        children: [
                          MessageBubble(message: msg),
                          if (!msg.isUser && msg.domainData != null)
                            DomainDataCard(
                              data: msg.domainData!,
                              appId: api.currentApp,
                            ),
                        ],
                      );
                    },
                  ),
          ),

          // Loading indicator
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 8),
                  Text('Processing...'),
                ],
              ),
            ),

          // Input bar
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: theme.colorScheme.surface,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 4,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: InputDecoration(
                        hintText: api.currentApp == 'asha_health'
                            ? 'e.g. राम 45 साल बुखार है'
                            : 'e.g. FIR kaise file kare?',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 12),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                      textInputAction: TextInputAction.send,
                    ),
                  ),
                  const SizedBox(width: 8),
                  FloatingActionButton(
                    onPressed: _isLoading ? null : _sendMessage,
                    mini: true,
                    child: const Icon(Icons.send),
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

class _AppChip extends StatelessWidget {
  final String appId;
  const _AppChip({required this.appId});

  @override
  Widget build(BuildContext context) {
    final isAsha = appId == 'asha_health';
    return Chip(
      label: Text(
        isAsha ? 'ASHA Health' : 'Lawyer AI',
        style: const TextStyle(fontSize: 12),
      ),
      avatar: Icon(
        isAsha ? Icons.local_hospital : Icons.gavel,
        size: 16,
        color: isAsha ? Colors.red : Colors.indigo,
      ),
      visualDensity: VisualDensity.compact,
    );
  }
}

class _EmptyState extends StatelessWidget {
  final String appId;
  const _EmptyState({required this.appId});

  @override
  Widget build(BuildContext context) {
    final isAsha = appId == 'asha_health';
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isAsha ? Icons.local_hospital : Icons.gavel,
            size: 64,
            color: Colors.grey.shade400,
          ),
          const SizedBox(height: 16),
          Text(
            isAsha ? 'ASHA Health Assistant' : 'Lawyer AI Assistant',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.grey.shade600,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            isAsha
                ? 'Type a patient visit in Hindi or English\ne.g. "राम 45 साल बुखार है"'
                : 'Ask a legal question\ne.g. "FIR kaise file kare?"',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey.shade500),
          ),
        ],
      ),
    );
  }
}
