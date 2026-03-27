class PlatformHealth {
  final String status;
  final String version;
  final List<String> pluginsLoaded;
  final ModelStatus modelStatus;

  PlatformHealth({
    required this.status,
    required this.version,
    required this.pluginsLoaded,
    required this.modelStatus,
  });

  factory PlatformHealth.fromJson(Map<String, dynamic> json) {
    return PlatformHealth(
      status: json['status'] ?? 'unknown',
      version: json['version'] ?? '',
      pluginsLoaded: List<String>.from(json['plugins_loaded'] ?? []),
      modelStatus: ModelStatus.fromJson(json['model_status'] ?? {}),
    );
  }
}

class ModelStatus {
  final int vramBudgetMb;
  final int systemReservedMb;
  final int modelReservedMb;
  final int availableMb;
  final String? activeModel;
  final String? activeModelTag;

  ModelStatus({
    required this.vramBudgetMb,
    required this.systemReservedMb,
    required this.modelReservedMb,
    required this.availableMb,
    this.activeModel,
    this.activeModelTag,
  });

  factory ModelStatus.fromJson(Map<String, dynamic> json) {
    return ModelStatus(
      vramBudgetMb: json['vram_budget_mb'] ?? 0,
      systemReservedMb: json['system_reserved_mb'] ?? 0,
      modelReservedMb: json['model_reserved_mb'] ?? 0,
      availableMb: json['available_mb'] ?? 0,
      activeModel: json['active_model'],
      activeModelTag: json['active_model_tag'],
    );
  }

  double get usagePercent {
    if (vramBudgetMb == 0) return 0;
    return (vramBudgetMb - availableMb) / vramBudgetMb;
  }
}
