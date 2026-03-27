class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final Map<String, dynamic>? domainData;
  final double? confidence;
  final int? processingMs;
  final String? error;

  ChatMessage({
    required this.text,
    required this.isUser,
    DateTime? timestamp,
    this.domainData,
    this.confidence,
    this.processingMs,
    this.error,
  }) : timestamp = timestamp ?? DateTime.now();
}
