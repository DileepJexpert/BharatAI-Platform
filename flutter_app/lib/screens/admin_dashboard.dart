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
  Map<String, dynamic>? _visits;

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
    setState(() => _isRefreshing = false);
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
                      _InfoRow('Plugins',
                          health.pluginsLoaded.join(', '), null),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // --- VRAM Usage ---
              _SectionHeader(title: 'GPU / VRAM'),
              _VRAMCard(modelStatus: health.modelStatus),

              const SizedBox(height: 16),

              // --- Loaded Model ---
              _SectionHeader(title: 'Active Model'),
              Card(
                child: ListTile(
                  leading: Icon(
                    Icons.memory,
                    color: health.modelStatus.activeModel != null
                        ? Colors.green
                        : Colors.grey,
                  ),
                  title: Text(
                    health.modelStatus.activeModelTag ?? 'No model loaded',
                  ),
                  subtitle: Text(
                    health.modelStatus.activeModel != null
                        ? '${health.modelStatus.modelReservedMb} MB VRAM'
                        : 'Load a model to start inference',
                  ),
                  trailing: health.modelStatus.activeModel != null
                      ? const Chip(
                          label: Text('WARM'),
                          backgroundColor: Colors.green,
                          labelStyle: TextStyle(
                              color: Colors.white, fontSize: 11),
                        )
                      : null,
                ),
              ),
            ],

            const SizedBox(height: 16),

            // --- Plugins ---
            if (health != null) ...[
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

// --- Widgets ---

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
                _VRAMLabel('System', modelStatus.systemReservedMb,
                    Colors.orange),
                _VRAMLabel(
                    'Model', modelStatus.modelReservedMb, Colors.blue),
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
                style: TextStyle(
                    color: Colors.grey.shade600, fontSize: 13)),
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
