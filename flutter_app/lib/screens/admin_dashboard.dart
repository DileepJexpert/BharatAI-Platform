import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../models/platform_health.dart';

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  bool _isRefreshing = false;
  bool _isSwitchingModel = false;
  Map<String, dynamic>? _visits;
  List<dynamic>? _availableModels;
  String? _activeModelKey;
  String? _switchMessage;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _isRefreshing = true);
    final api = context.read<ApiService>();
    await api.checkHealth();
    try {
      _visits = await api.listVisits();
    } catch (_) {}
    try {
      final modelData = await api.getAvailableModels();
      _availableModels = modelData['models'] as List?;
      _activeModelKey = modelData['active_model'] as String?;
    } catch (_) {}
    setState(() => _isRefreshing = false);
  }

  Future<void> _switchModel(String modelKey) async {
    setState(() {
      _isSwitchingModel = true;
      _switchMessage = null;
    });
    final api = context.read<ApiService>();
    try {
      final result = await api.switchModel(modelKey);
      setState(() {
        _activeModelKey = modelKey;
        _switchMessage = result['message'] as String?;
        if (result['pull_command'] != null) {
          _switchMessage =
              '$_switchMessage\n\nIf model not downloaded, run:\n${result['pull_command']}';
        }
      });
      await _refresh();
    } catch (e) {
      setState(() {
        _switchMessage = 'Error: $e';
      });
    } finally {
      setState(() => _isSwitchingModel = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.watch<ApiService>();
    final health = api.health;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Dashboard'),
        actions: [
          IconButton(
            icon: _isRefreshing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            onPressed: _isRefreshing ? null : _refresh,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // --- Connection Status ---
            _StatusCard(
              isConnected: api.isConnected,
              baseUrl: api.baseUrl,
              onRetry: () => api.checkHealth(),
            ),

            const SizedBox(height: 16),

            // --- Platform Info ---
            if (health != null) ...[
              _SectionHeader(title: 'Platform'),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _InfoRow('Status', health.status, Colors.green),
                      _InfoRow('Version', health.version, null),
                      _InfoRow(
                          'Plugins', health.pluginsLoaded.join(', '), null),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // --- VRAM Usage ---
              _SectionHeader(title: 'GPU / VRAM'),
              _VRAMCard(modelStatus: health.modelStatus),

              const SizedBox(height: 16),

              // ============================================
              // --- MODEL SELECTOR (NEW) ---
              // ============================================
              _SectionHeader(title: 'Switch AI Model'),
              _ModelSelectorCard(
                availableModels: _availableModels,
                activeModelKey: _activeModelKey,
                isSwitching: _isSwitchingModel,
                switchMessage: _switchMessage,
                onSwitch: _switchModel,
                vramBudget: health.modelStatus.vramBudgetMb,
              ),

              const SizedBox(height: 16),

              // --- Plugins ---
              _SectionHeader(title: 'Plugins'),
              ...health.pluginsLoaded.map((p) => Card(
                    child: ListTile(
                      leading: Icon(
                        p == 'asha_health'
                            ? Icons.local_hospital
                            : Icons.gavel,
                        color:
                            p == 'asha_health' ? Colors.red : Colors.indigo,
                      ),
                      title: Text(
                        p == 'asha_health' ? 'ASHA Health' : 'Lawyer AI',
                      ),
                      subtitle: Text('/$p/voice  /$p/chat'),
                      trailing: const Icon(Icons.check_circle,
                          color: Colors.green, size: 20),
                    ),
                  )),
            ],

            const SizedBox(height: 16),

            // --- Recent Visits (ASHA) ---
            _SectionHeader(title: 'Recent Visits (ASHA)'),
            if (_visits != null) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Total: ${_visits!['count'] ?? 0}',
                        style: theme.textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      if ((_visits!['visits'] as List?)?.isNotEmpty == true)
                        ...(_visits!['visits'] as List)
                            .take(5)
                            .map((v) => ListTile(
                                  dense: true,
                                  title: Text(
                                      v['patient_name'] ?? 'Unknown'),
                                  subtitle: Text(
                                      '${v['complaint'] ?? '-'} | ${v['visit_date'] ?? '-'}'),
                                  trailing: _SyncChip(
                                      status: v['sync_status'] ?? 'pending'),
                                ))
                      else
                        const Text('No visits recorded yet.',
                            style: TextStyle(color: Colors.grey)),
                    ],
                  ),
                ),
              ),
            ] else
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Could not load visits.',
                      style: TextStyle(color: Colors.grey)),
                ),
              ),

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

// ============================================
// MODEL SELECTOR CARD
// ============================================

class _ModelSelectorCard extends StatelessWidget {
  final List<dynamic>? availableModels;
  final String? activeModelKey;
  final bool isSwitching;
  final String? switchMessage;
  final Function(String) onSwitch;
  final int vramBudget;

  const _ModelSelectorCard({
    required this.availableModels,
    required this.activeModelKey,
    required this.isSwitching,
    required this.switchMessage,
    required this.onSwitch,
    required this.vramBudget,
  });

  @override
  Widget build(BuildContext context) {
    if (availableModels == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('Loading models...', style: TextStyle(color: Colors.grey)),
        ),
      );
    }

    final freeModels =
        availableModels!.where((m) => m['category'] == 'free').toList();
    final paidModels =
        availableModels!.where((m) => m['category'] == 'paid').toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current model display
            Row(
              children: [
                const Icon(Icons.memory, color: Colors.blue),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Current Model',
                          style: TextStyle(fontSize: 12, color: Colors.grey)),
                      Text(
                        _getDisplayName(activeModelKey),
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
                if (isSwitching)
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),

            if (switchMessage != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: switchMessage!.startsWith('Error')
                      ? Colors.red.shade50
                      : Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  switchMessage!,
                  style: TextStyle(
                    fontSize: 12,
                    color: switchMessage!.startsWith('Error')
                        ? Colors.red.shade700
                        : Colors.green.shade700,
                  ),
                ),
              ),
            ],

            const Divider(height: 24),

            // Free models section
            Text('Free Models (Local GPU)',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.green.shade700)),
            const SizedBox(height: 8),
            ...freeModels.map((m) => _ModelTile(
                  model: m,
                  isActive: m['model_key'] == activeModelKey,
                  isSwitching: isSwitching,
                  onTap: () => onSwitch(m['model_key'] as String),
                )),

            if (paidModels.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text('Cloud Models (Paid — Coming Soon)',
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.purple.shade700)),
              const SizedBox(height: 8),
              ...paidModels.map((m) => _ModelTile(
                    model: m,
                    isActive: m['model_key'] == activeModelKey,
                    isSwitching: true, // disabled for now
                    onTap: () {},
                    isPaid: true,
                  )),
            ],
          ],
        ),
      ),
    );
  }

  String _getDisplayName(String? key) {
    if (key == null) return 'No model loaded';
    final model = availableModels?.firstWhere(
      (m) => m['model_key'] == key,
      orElse: () => {'display_name': key},
    );
    return model?['display_name'] ?? key;
  }
}

class _ModelTile extends StatelessWidget {
  final Map<String, dynamic> model;
  final bool isActive;
  final bool isSwitching;
  final VoidCallback onTap;
  final bool isPaid;

  const _ModelTile({
    required this.model,
    required this.isActive,
    required this.isSwitching,
    required this.onTap,
    this.isPaid = false,
  });

  @override
  Widget build(BuildContext context) {
    final canLoad = model['can_load'] == true;
    final vramMb = model['vram_mb'] as int? ?? 0;
    final name = model['display_name'] as String? ?? model['model_key'];
    final desc = model['description'] as String? ?? '';

    return InkWell(
      onTap: (isActive || isSwitching || !canLoad || isPaid) ? null : onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          border: Border.all(
            color: isActive ? Colors.blue : Colors.grey.shade300,
            width: isActive ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(8),
          color: isActive
              ? Colors.blue.shade50
              : isPaid
                  ? Colors.grey.shade50
                  : null,
        ),
        child: Row(
          children: [
            // Radio-like indicator
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: isActive ? Colors.blue : Colors.grey.shade400,
                  width: 2,
                ),
                color: isActive ? Colors.blue : Colors.transparent,
              ),
              child: isActive
                  ? const Icon(Icons.check, size: 14, color: Colors.white)
                  : null,
            ),
            const SizedBox(width: 12),
            // Model info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      fontSize: 14,
                      color: isPaid ? Colors.grey : null,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    desc,
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
            // VRAM badge
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: canLoad
                        ? Colors.green.shade100
                        : Colors.red.shade100,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    vramMb > 0 ? '${(vramMb / 1000).toStringAsFixed(1)}GB' : 'Cloud',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color:
                          canLoad ? Colors.green.shade700 : Colors.red.shade700,
                    ),
                  ),
                ),
                if (!canLoad && !isPaid)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text('Too large',
                        style: TextStyle(
                            fontSize: 10, color: Colors.red.shade400)),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// --- Existing widgets ---

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        title,
        style: Theme.of(context)
            .textTheme
            .titleSmall
            ?.copyWith(color: Colors.grey.shade600),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final bool isConnected;
  final String baseUrl;
  final VoidCallback onRetry;

  const _StatusCard({
    required this.isConnected,
    required this.baseUrl,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: isConnected ? Colors.green.shade50 : Colors.red.shade50,
      child: ListTile(
        leading: Icon(
          isConnected ? Icons.cloud_done : Icons.cloud_off,
          color: isConnected ? Colors.green : Colors.red,
        ),
        title: Text(isConnected ? 'Connected' : 'Disconnected'),
        subtitle: Text(baseUrl),
        trailing: isConnected
            ? null
            : TextButton(onPressed: onRetry, child: const Text('RETRY')),
      ),
    );
  }
}

class _VRAMCard extends StatelessWidget {
  final ModelStatus modelStatus;
  const _VRAMCard({required this.modelStatus});

  @override
  Widget build(BuildContext context) {
    final used = modelStatus.vramBudgetMb - modelStatus.availableMb;
    final total = modelStatus.vramBudgetMb;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('VRAM Usage',
                    style: Theme.of(context).textTheme.titleSmall),
                Text('$used / $total MB'),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: modelStatus.usagePercent,
                minHeight: 12,
                backgroundColor: Colors.grey.shade200,
                color: modelStatus.usagePercent > 0.85
                    ? Colors.red
                    : Colors.blue,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 16,
              children: [
                _VRAMLabel(
                    'System', modelStatus.systemReservedMb, Colors.orange),
                _VRAMLabel('Model', modelStatus.modelReservedMb, Colors.blue),
                _VRAMLabel('Free', modelStatus.availableMb, Colors.green),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _VRAMLabel extends StatelessWidget {
  final String label;
  final int mb;
  final Color color;
  const _VRAMLabel(this.label, this.mb, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text('$label: ${mb}MB', style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const _InfoRow(this.label, this.value, this.valueColor);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
                style:
                    TextStyle(color: Colors.grey.shade600, fontSize: 13)),
          ),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.w500,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _SyncChip extends StatelessWidget {
  final String status;
  const _SyncChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'synced' => Colors.green,
      'failed' => Colors.red,
      _ => Colors.orange,
    };
    return Chip(
      label: Text(status, style: const TextStyle(fontSize: 10)),
      backgroundColor: color.withValues(alpha: 0.15),
      labelStyle: TextStyle(color: color),
      visualDensity: VisualDensity.compact,
    );
  }
}
