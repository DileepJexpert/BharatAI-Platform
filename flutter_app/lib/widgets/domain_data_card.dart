import 'package:flutter/material.dart';

class DomainDataCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final String appId;

  const DomainDataCard({
    super.key,
    required this.data,
    required this.appId,
  });

  @override
  Widget build(BuildContext context) {
    if (appId == 'asha_health') {
      return _AshaDataCard(data: data);
    } else if (appId == 'lawyer_ai') {
      return _LawyerDataCard(data: data);
    }
    return _GenericDataCard(data: data);
  }
}

class _AshaDataCard extends StatelessWidget {
  final Map<String, dynamic> data;
  const _AshaDataCard({required this.data});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(left: 0, right: 48, top: 4, bottom: 4),
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.local_hospital, size: 16, color: Colors.red.shade700),
                const SizedBox(width: 6),
                Text(
                  'Patient Visit',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: Colors.red.shade700,
                  ),
                ),
              ],
            ),
            const Divider(height: 16),
            if (data['patient_name'] != null)
              _DataRow('Patient', data['patient_name'].toString()),
            if (data['age'] != null)
              _DataRow('Age', '${data['age']}'),
            if (data['gender'] != null)
              _DataRow('Gender', data['gender'].toString()),
            if (data['complaint'] != null)
              _DataRow('Complaint', data['complaint'].toString()),
            if (data['symptoms'] != null && data['symptoms'] is List)
              _DataRow('Symptoms', (data['symptoms'] as List).join(', ')),
            if (data['temperature'] != null)
              _DataRow('Temp', '${data['temperature']}'),
            if (data['bp'] != null)
              _DataRow('BP', data['bp'].toString()),
            if (data['visit_date'] != null)
              _DataRow('Date', data['visit_date'].toString()),
          ],
        ),
      ),
    );
  }
}

class _LawyerDataCard extends StatelessWidget {
  final Map<String, dynamic> data;
  const _LawyerDataCard({required this.data});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(left: 0, right: 48, top: 4, bottom: 4),
      color: Colors.indigo.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.gavel, size: 16, color: Colors.indigo.shade700),
                const SizedBox(width: 6),
                Text(
                  'Legal Info',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: Colors.indigo.shade700,
                  ),
                ),
              ],
            ),
            const Divider(height: 16),
            if (data['sections_cited'] != null && data['sections_cited'] is List)
              _DataRow(
                  'Sections', (data['sections_cited'] as List).join(', ')),
            if (data['severity'] != null)
              _DataRow('Severity', data['severity'].toString()),
            if (data['needs_lawyer'] != null)
              _DataRow(
                'Needs Lawyer',
                data['needs_lawyer'] == true ? 'Yes' : 'No',
              ),
          ],
        ),
      ),
    );
  }
}

class _GenericDataCard extends StatelessWidget {
  final Map<String, dynamic> data;
  const _GenericDataCard({required this.data});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(left: 0, right: 48, top: 4, bottom: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: data.entries
              .map((e) => _DataRow(e.key, e.value.toString()))
              .toList(),
        ),
      ),
    );
  }
}

class _DataRow extends StatelessWidget {
  final String label;
  final String value;
  const _DataRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
