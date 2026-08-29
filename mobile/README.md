# DocPilot Mobile

Flutter implementation for Android and iOS with role-separated patient and doctor experiences.

## Included

- Patient dashboard, pre-visit status, records and medication history
- Camera scanning through `image_picker`
- PDF/image/document upload through `file_picker`
- Doctor queue, evidence-backed clinical summary, alerts and review tasks
- Role switch for demonstrating both experiences
- Patient-facing screens contain no diagnostic AI features

## Run

Install Flutter, then from this directory:

```bash
flutter create . --platforms=android,ios,web
flutter pub get
flutter run
```

For iOS, add camera and photo-library descriptions to `ios/Runner/Info.plist`. For Android, the generated project and picker plugins handle the standard picker permissions.

This is a functional frontend prototype. Authentication, encrypted uploads, OCR, clinical extraction, consent, audit logging, and persistent records need to be connected to the production backend.
