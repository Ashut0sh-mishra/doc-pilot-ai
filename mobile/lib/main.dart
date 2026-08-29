import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

void main() => runApp(const DocPilotApp());

const ink = Color(0xFF172725);
const forest = Color(0xFF176858);
const mint = Color(0xFFE7F2EE);
const canvas = Color(0xFFF5F7F4);
const muted = Color(0xFF71807C);
const line = Color(0xFFE2E8E4);

class DocPilotApp extends StatelessWidget {
  const DocPilotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'DocPilot',
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: canvas,
        colorScheme: ColorScheme.fromSeed(seedColor: forest, primary: forest),
        fontFamily: 'sans-serif',
        cardTheme: const CardThemeData(
          color: Colors.white,
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            side: BorderSide(color: line),
            borderRadius: BorderRadius.all(Radius.circular(18)),
          ),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: line),
          ),
        ),
      ),
      home: const RoleGate(),
    );
  }
}

class RoleGate extends StatefulWidget {
  const RoleGate({super.key});
  @override
  State<RoleGate> createState() => _RoleGateState();
}

class _RoleGateState extends State<RoleGate> {
  bool doctor = false;

  @override
  Widget build(BuildContext context) => doctor
      ? DoctorShell(onSwitch: () => setState(() => doctor = false))
      : PatientShell(onSwitch: () => setState(() => doctor = true));
}

class PatientShell extends StatefulWidget {
  const PatientShell({super.key, required this.onSwitch});
  final VoidCallback onSwitch;
  @override
  State<PatientShell> createState() => _PatientShellState();
}

class _PatientShellState extends State<PatientShell> {
  int index = 0;
  final records = <MedicalRecord>[
    MedicalRecord('Cardiology consultation', 'Consultation · 12 Aug 2026', Icons.description_outlined, const Color(0xFFE7EFF6)),
    MedicalRecord('Complete blood count', 'Lab report · 09 Aug 2026', Icons.science_outlined, const Color(0xFFEEEAF6)),
    MedicalRecord('Metformin strip', 'Medicine photo · Today', Icons.medication_outlined, const Color(0xFFFBECDD)),
  ];

  Future<void> addCamera() async {
    final photo = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 82);
    if (photo == null || !mounted) return;
    setState(() => records.insert(0, MedicalRecord(photo.name, 'Photo · Added now', Icons.image_outlined, mint)));
    message(context, 'Photo securely added to your records');
  }

  Future<void> addFiles() async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: true, type: FileType.custom, allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']);
    if (result == null || !mounted) return;
    setState(() {
      for (final file in result.files.reversed) {
        records.insert(0, MedicalRecord(file.name, 'Document · Added now', Icons.description_outlined, mint));
      }
    });
    message(context, '${result.files.length} file${result.files.length == 1 ? '' : 's'} added');
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      PatientHome(onCamera: addCamera, onFiles: addFiles),
      RecordsPage(records: records, onCamera: addCamera, onFiles: addFiles),
      const MedicinesPage(),
      ProfilePage(onSwitch: widget.onSwitch),
    ];
    return Scaffold(
      body: SafeArea(child: pages[index]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.folder_outlined), selectedIcon: Icon(Icons.folder), label: 'Records'),
          NavigationDestination(icon: Icon(Icons.medication_outlined), selectedIcon: Icon(Icons.medication), label: 'Medicines'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}

class PatientHome extends StatelessWidget {
  const PatientHome({super.key, required this.onCamera, required this.onFiles});
  final VoidCallback onCamera;
  final VoidCallback onFiles;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
    children: [
      AppHeader(title: 'Good afternoon, Arun', subtitle: 'Your health records, in one place', avatar: 'AK'),
      const SizedBox(height: 24),
      Card(child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(width: 46, height: 46, decoration: BoxDecoration(color: mint, borderRadius: BorderRadius.circular(13)), child: const Icon(Icons.calendar_month_outlined, color: forest)),
            const SizedBox(width: 13),
            const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('TODAY · 4:30 PM', style: TextStyle(color: forest, fontSize: 11, fontWeight: FontWeight.w700)), SizedBox(height: 3), Text('Dr. Rhea Menon', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17)), Text('Internal Medicine', style: TextStyle(color: muted, fontSize: 12))])),
            const Icon(Icons.chevron_right, color: muted),
          ]),
          const Divider(height: 30),
          const Text('Your pre-visit check-in is almost ready', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const LinearProgressIndicator(value: .72, minHeight: 7, borderRadius: BorderRadius.all(Radius.circular(10)), backgroundColor: Color(0xFFE6EBE8)),
          const SizedBox(height: 7),
          const Text('Add any recent reports or medicine photos', style: TextStyle(color: muted, fontSize: 11)),
          const SizedBox(height: 14),
          FilledButton(onPressed: onCamera, child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.document_scanner_outlined, size: 19), SizedBox(width: 8), Text('Scan a medical record')]))
        ]),
      )),
      const SectionTitle('Quick actions'),
      Row(children: [
        Expanded(child: ActionTile(icon: Icons.camera_alt_outlined, title: 'Take photo', subtitle: 'Report or strip', onTap: onCamera)),
        const SizedBox(width: 10),
        Expanded(child: ActionTile(icon: Icons.upload_file_outlined, title: 'Upload file', subtitle: 'PDF or image', onTap: onFiles)),
      ]),
      const SectionTitle('Health at a glance'),
      Card(child: Column(children: const [
        HealthRow(icon: Icons.medication_outlined, title: '5 current medicines', subtitle: '1 needs confirmation', color: Color(0xFFF4A261)),
        Divider(height: 1, indent: 60),
        HealthRow(icon: Icons.warning_amber_rounded, title: 'Penicillin allergy', subtitle: 'Recorded allergy', color: Color(0xFFC25757)),
        Divider(height: 1, indent: 60),
        HealthRow(icon: Icons.folder_copy_outlined, title: '12 medical records', subtitle: 'From the last 2.5 years', color: forest),
      ])),
      const SizedBox(height: 18),
      const PrivacyNote(),
    ],
  );
}

class RecordsPage extends StatelessWidget {
  const RecordsPage({super.key, required this.records, required this.onCamera, required this.onFiles});
  final List<MedicalRecord> records;
  final VoidCallback onCamera;
  final VoidCallback onFiles;

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.fromLTRB(20, 18, 20, 32), children: [
    const AppHeader(title: 'My medical records', subtitle: 'Documents, tests and medicine photos', avatar: 'AK'),
    const SizedBox(height: 22),
    Row(children: [Expanded(child: FilledButton.icon(onPressed: onCamera, icon: const Icon(Icons.document_scanner_outlined), label: const Text('Scan'))), const SizedBox(width: 9), Expanded(child: OutlinedButton.icon(onPressed: onFiles, icon: const Icon(Icons.upload_file_outlined), label: const Text('Upload')))]),
    const SizedBox(height: 17),
    const TextField(decoration: InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search your records')),
    const SectionTitle('All records'),
    Card(child: ListView.separated(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: records.length, separatorBuilder: (_, __) => const Divider(height: 1, indent: 68), itemBuilder: (_, i) {
      final r = records[i];
      return ListTile(contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5), leading: Container(width: 42, height: 42, decoration: BoxDecoration(color: r.color, borderRadius: BorderRadius.circular(11)), child: Icon(r.icon, color: forest)), title: Text(r.title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)), subtitle: Text(r.meta, style: const TextStyle(fontSize: 10)), trailing: const Icon(Icons.more_vert, size: 19));
    })),
    const SizedBox(height: 18),
    const PrivacyNote(),
  ]);
}

class MedicinesPage extends StatelessWidget {
  const MedicinesPage({super.key});
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.fromLTRB(20, 18, 20, 32), children: [
    const AppHeader(title: 'My medicines', subtitle: 'Keep an accurate medication history', avatar: 'AK'),
    const SizedBox(height: 20),
    Card(color: const Color(0xFFFFF8ED), child: const Padding(padding: EdgeInsets.all(15), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.info_outline, color: Color(0xFFA9642B)), SizedBox(width: 10), Expanded(child: Text('This list is for record keeping. Do not start, stop, or change a medicine without speaking to your clinician.', style: TextStyle(fontSize: 11, height: 1.45, color: Color(0xFF765534))))]))),
    const SectionTitle('Current medicines'),
    Card(child: Column(children: const [
      MedicineRow('Metformin', '500 mg · Twice daily', true), Divider(height: 1, indent: 65),
      MedicineRow('Amlodipine', '10 mg · Once daily', true), Divider(height: 1, indent: 65),
      MedicineRow('Atorvastatin', '20 mg · At night', true), Divider(height: 1, indent: 65),
      MedicineRow('Telmisartan', '40 mg · Frequency not added', false),
    ])),
    const SizedBox(height: 15),
    OutlinedButton.icon(onPressed: () => message(context, 'Medicine entry form opened'), icon: const Icon(Icons.add), label: const Text('Add a medicine')),
    const SectionTitle('Previous medicines'),
    Card(child: ListTile(leading: const Icon(Icons.history, color: forest), title: const Text('View medication history', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)), subtitle: const Text('Changes, stopped medicines and old prescriptions', style: TextStyle(fontSize: 10)), trailing: const Icon(Icons.chevron_right))),
  ]);
}

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key, required this.onSwitch});
  final VoidCallback onSwitch;
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
    const SizedBox(height: 12),
    const CircleAvatar(radius: 35, backgroundColor: mint, foregroundColor: forest, child: Text('AK', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold))),
    const SizedBox(height: 10),
    const Center(child: Text('Arun Kumar', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold))),
    const Center(child: Text('Patient ID DP-2048', style: TextStyle(color: muted, fontSize: 11))),
    const SectionTitle('Account'),
    Card(child: Column(children: [
      const ListTile(leading: Icon(Icons.person_outline), title: Text('Personal details'), trailing: Icon(Icons.chevron_right)),
      const Divider(height: 1, indent: 55),
      const ListTile(leading: Icon(Icons.shield_outlined), title: Text('Privacy and access'), trailing: Icon(Icons.chevron_right)),
      const Divider(height: 1, indent: 55),
      ListTile(onTap: onSwitch, leading: const Icon(Icons.stethoscope_outlined), title: const Text('Open doctor demo'), subtitle: const Text('Prototype role switch'), trailing: const Icon(Icons.swap_horiz)),
    ])),
  ]);
}

class DoctorShell extends StatefulWidget {
  const DoctorShell({super.key, required this.onSwitch});
  final VoidCallback onSwitch;
  @override
  State<DoctorShell> createState() => _DoctorShellState();
}

class _DoctorShellState extends State<DoctorShell> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final pages = [const DoctorDashboard(), const PatientSummary(), const DoctorTasks(), DoctorProfile(onSwitch: widget.onSwitch)];
    return Scaffold(
      body: SafeArea(child: pages[index]),
      bottomNavigationBar: NavigationBar(selectedIndex: index, onDestinationSelected: (v) => setState(() => index = v), destinations: const [
        NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Dashboard'),
        NavigationDestination(icon: Icon(Icons.people_outline), selectedIcon: Icon(Icons.people), label: 'Patients'),
        NavigationDestination(icon: Icon(Icons.task_alt_outlined), selectedIcon: Icon(Icons.task_alt), label: 'Tasks'),
        NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
      ]),
    );
  }
}

class DoctorDashboard extends StatelessWidget {
  const DoctorDashboard({super.key});
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.fromLTRB(20, 18, 20, 32), children: [
    const AppHeader(title: 'Good afternoon, Dr. Menon', subtitle: '4 patients are ready for review', avatar: 'DR'),
    const SizedBox(height: 22),
    const TextField(decoration: InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search patients')),
    const SectionTitle('Next appointment'),
    Card(child: Padding(padding: const EdgeInsets.all(17), child: Column(children: [
      const Row(children: [CircleAvatar(backgroundColor: mint, foregroundColor: forest, child: Text('AK')), SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Arun Kumar', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)), Text('58 years · Male · 4:30 PM', style: TextStyle(color: muted, fontSize: 11))])), StatusPill('Ready')]),
      const Divider(height: 28),
      const Row(children: [Expanded(child: MiniMetric('12', 'Records')), Expanded(child: MiniMetric('2', 'Record gaps')), Expanded(child: MiniMetric('3', 'Alerts'))]),
      const SizedBox(height: 15),
      FilledButton(onPressed: () => message(context, 'Open Patients to review Arun Kumar'), child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.auto_awesome, size: 18), SizedBox(width: 7), Text('Review clinical summary')]))
    ]))),
    const SectionTitle('Today’s queue'),
    ...['Meera Shah · 5:00 PM', 'Kabir Rao · 5:30 PM', 'Nisha Patel · 6:00 PM'].map((x) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Card(child: ListTile(leading: CircleAvatar(backgroundColor: const Color(0xFFEDF1EF), child: Text(x.substring(0, 1))), title: Text(x.split(' · ')[0], style: const TextStyle(fontWeight: FontWeight.w600)), subtitle: Text(x.split(' · ')[1]), trailing: const Icon(Icons.chevron_right))))),
  ]);
}

class PatientSummary extends StatelessWidget {
  const PatientSummary({super.key});
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.fromLTRB(20, 18, 20, 32), children: [
    const AppHeader(title: 'Arun Kumar', subtitle: '58 years · Male · DP-2048', avatar: 'AK'),
    const SizedBox(height: 18),
    Card(color: const Color(0xFFFFF8ED), child: const ListTile(leading: Icon(Icons.warning_amber_rounded, color: Color(0xFFA9642B)), title: Text('2 important record gaps', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)), subtitle: Text('Latest ECG and renal follow-up are missing', style: TextStyle(fontSize: 10)), trailing: Icon(Icons.chevron_right))),
    const SectionTitle('Clinical snapshot'),
    Card(child: Padding(padding: const EdgeInsets.all(17), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Row(children: [Icon(Icons.auto_awesome, color: forest, size: 18), SizedBox(width: 7), Text('AI-ASSISTED SYNTHESIS', style: TextStyle(fontSize: 9, color: forest, fontWeight: FontWeight.bold, letterSpacing: .7))]),
      const SizedBox(height: 11),
      const Text('58-year-old male with poorly controlled type 2 diabetes and hypertension, now reporting progressive fatigue and bilateral ankle swelling for 3 weeks.', style: TextStyle(fontSize: 13, height: 1.55)),
      const Divider(height: 27),
      const Row(children: [Icon(Icons.shield_outlined, size: 17, color: forest), SizedBox(width: 7), Expanded(child: Text('Evidence coverage: 82% · 9 verified and 3 patient-provided sources', style: TextStyle(fontSize: 9, color: muted)))]),
    ]))),
    const SectionTitle('Needs attention'),
    const ClinicalAlert(color: Color(0xFFC55750), icon: Icons.medication_outlined, title: 'Possible medication conflict', body: 'Amlodipine dose differs between the consultation and medicine photo.'),
    const SizedBox(height: 8),
    const ClinicalAlert(color: Color(0xFFB36B31), icon: Icons.schedule, title: 'Follow-up appears overdue', body: 'Renal function repeat was advised; no result was found.'),
    const SectionTitle('Active conditions'),
    Card(child: Column(children: const [ConditionRow('Type 2 diabetes mellitus', 'Needs attention', Color(0xFFC55750)), Divider(height: 1, indent: 25), ConditionRow('Essential hypertension', 'Suboptimal control', Color(0xFFB36B31)), Divider(height: 1, indent: 25), ConditionRow('Mild anaemia', 'Investigate', Color(0xFF7257A9)), Divider(height: 1, indent: 25), ConditionRow('Dyslipidaemia', 'Stable', forest)])),
    const SectionTitle('Decision support'),
    Card(color: const Color(0xFFF0F6F3), child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Suggested review areas', style: TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      const Text('Use clinical judgement. Suggestions are not final orders.', style: TextStyle(color: muted, fontSize: 10)),
      ...['Assess oedema and heart failure signs', 'Review glycaemic control plan', 'Reconcile current medicines', 'Consider renal and anaemia work-up'].map((x) => CheckboxListTile(contentPadding: EdgeInsets.zero, dense: true, controlAffinity: ListTileControlAffinity.leading, value: false, onChanged: (_) {}, title: Text(x, style: const TextStyle(fontSize: 11)))),
      FilledButton(onPressed: () => message(context, 'Draft plan created for clinical review'), child: const Center(child: Text('Create draft consultation plan'))),
    ]))),
    const SizedBox(height: 16),
    const PrivacyNote(text: 'Clinician decision support only. Verify all source data with the patient.'),
  ]);
}

class DoctorTasks extends StatelessWidget {
  const DoctorTasks({super.key});
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
    const AppHeader(title: 'Clinical tasks', subtitle: 'Items requiring your review', avatar: 'DR'),
    const SectionTitle('Open tasks'),
    ...['Reconcile Arun Kumar’s medicines', 'Review Meera Shah’s uploaded scan', 'Confirm Kabir Rao’s allergy history'].map((t) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Card(child: CheckboxListTile(value: false, onChanged: (_) {}, title: Text(t, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)), subtitle: const Text('Due today', style: TextStyle(fontSize: 10)), controlAffinity: ListTileControlAffinity.leading)))),
  ]);
}

class DoctorProfile extends StatelessWidget {
  const DoctorProfile({super.key, required this.onSwitch});
  final VoidCallback onSwitch;
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
    const SizedBox(height: 15), const CircleAvatar(radius: 35, backgroundColor: mint, foregroundColor: forest, child: Text('DR', style: TextStyle(fontWeight: FontWeight.bold))),
    const SizedBox(height: 10), const Center(child: Text('Dr. Rhea Menon', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 20))), const Center(child: Text('Internal Medicine', style: TextStyle(color: muted))),
    const SectionTitle('Workspace'),
    Card(child: ListTile(onTap: onSwitch, leading: const Icon(Icons.swap_horiz, color: forest), title: const Text('Open patient demo'), subtitle: const Text('Prototype role switch'), trailing: const Icon(Icons.chevron_right))),
  ]);
}

class AppHeader extends StatelessWidget {
  const AppHeader({super.key, required this.title, required this.subtitle, required this.avatar});
  final String title, subtitle, avatar;
  @override
  Widget build(BuildContext context) => Row(children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: ink)), const SizedBox(height: 2), Text(subtitle, style: const TextStyle(fontSize: 11, color: muted))])), CircleAvatar(backgroundColor: mint, foregroundColor: forest, child: Text(avatar, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)))]);
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key}); final String text;
  @override Widget build(BuildContext context) => Padding(padding: const EdgeInsets.fromLTRB(2, 24, 0, 10), child: Text(text, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)));
}

class ActionTile extends StatelessWidget {
  const ActionTile({super.key, required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon; final String title, subtitle; final VoidCallback onTap;
  @override Widget build(BuildContext context) => Card(child: InkWell(borderRadius: BorderRadius.circular(18), onTap: onTap, child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Container(width: 39, height: 39, decoration: BoxDecoration(color: mint, borderRadius: BorderRadius.circular(11)), child: Icon(icon, color: forest)), const SizedBox(height: 11), Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)), Text(subtitle, style: const TextStyle(color: muted, fontSize: 10))]))));
}

class HealthRow extends StatelessWidget {
  const HealthRow({super.key, required this.icon, required this.title, required this.subtitle, required this.color});
  final IconData icon; final String title, subtitle; final Color color;
  @override Widget build(BuildContext context) => ListTile(leading: Container(width: 38, height: 38, decoration: BoxDecoration(color: color.withValues(alpha: .12), borderRadius: BorderRadius.circular(10)), child: Icon(icon, color: color, size: 20)), title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)), subtitle: Text(subtitle, style: const TextStyle(fontSize: 10)), trailing: const Icon(Icons.chevron_right, size: 20));
}

class MedicineRow extends StatelessWidget {
  const MedicineRow(this.name, this.dose, this.verified, {super.key}); final String name, dose; final bool verified;
  @override Widget build(BuildContext context) => ListTile(leading: Container(width: 38, height: 38, decoration: BoxDecoration(color: mint, borderRadius: BorderRadius.circular(10)), child: const Icon(Icons.medication_outlined, color: forest)), title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)), subtitle: Text(dose, style: const TextStyle(fontSize: 10)), trailing: Icon(verified ? Icons.verified_outlined : Icons.warning_amber_rounded, color: verified ? forest : const Color(0xFFB36B31), size: 19));
}

class MiniMetric extends StatelessWidget {
  const MiniMetric(this.value, this.label, {super.key}); final String value, label;
  @override Widget build(BuildContext context) => Column(children: [Text(value, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold)), Text(label, style: const TextStyle(fontSize: 9, color: muted))]);
}

class StatusPill extends StatelessWidget {
  const StatusPill(this.text, {super.key}); final String text;
  @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), decoration: BoxDecoration(color: mint, borderRadius: BorderRadius.circular(20)), child: Text(text, style: const TextStyle(fontSize: 9, color: forest, fontWeight: FontWeight.bold)));
}

class ClinicalAlert extends StatelessWidget {
  const ClinicalAlert({super.key, required this.color, required this.icon, required this.title, required this.body}); final Color color; final IconData icon; final String title, body;
  @override Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(14), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Container(width: 38, height: 38, decoration: BoxDecoration(color: color.withValues(alpha: .12), borderRadius: BorderRadius.circular(10)), child: Icon(icon, color: color, size: 20)), const SizedBox(width: 11), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)), const SizedBox(height: 4), Text(body, style: const TextStyle(fontSize: 10, color: muted, height: 1.45)), const SizedBox(height: 6), const Text('Review →', style: TextStyle(color: forest, fontSize: 10, fontWeight: FontWeight.bold))]))])));
}

class ConditionRow extends StatelessWidget {
  const ConditionRow(this.name, this.status, this.color, {super.key}); final String name, status; final Color color;
  @override Widget build(BuildContext context) => ListTile(dense: true, leading: Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)), title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)), trailing: Text(status, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w600)));
}

class PrivacyNote extends StatelessWidget {
  const PrivacyNote({super.key, this.text = 'Your records are encrypted and shared only with authorised care providers.'}); final String text;
  @override Widget build(BuildContext context) => Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.shield_outlined, color: forest, size: 15), const SizedBox(width: 5), Flexible(child: Text(text, textAlign: TextAlign.center, style: const TextStyle(fontSize: 9, color: muted)))]);
}

class MedicalRecord {
  MedicalRecord(this.title, this.meta, this.icon, this.color);
  final String title, meta; final IconData icon; final Color color;
}

void message(BuildContext context, String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text), behavior: SnackBarBehavior.floating));
