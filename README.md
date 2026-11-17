# MOHANO-SERVER

MOHANO 앱의 인증, 프로필, 매칭, 채팅, P2P 음성 통화 signaling을 위한 FastAPI 서버다.
음성 미디어는 WebRTC P2P로 앱 간에 직접 전달하며, 이 서버는 오디오를 중계하지 않는다.

## 현재 범위

- `GET /v1/health`
- Swagger UI: `/v1/docs`, OpenAPI schema: `/v1/openapi.json`, ReDoc: `/v1/redoc`.
  Local docs are open; dev/staging require HTTP Basic Auth (`mohano-admin` plus the
  generated Secret Manager password); production docs are disabled.
- Google·Apple·LINE identity token 및 Kakao access token 검증과 access/refresh JWT 발급·갱신·로그아웃
- 프로필 텍스트·사진 참조값은 MySQL에 저장되며, 사진 원본은 private S3 호환 object storage에 둔다.
- 매칭 조건·후보, 통화 신청·P2P signaling, REST 채팅·읽음 API
- 매칭·채팅·통화 신청·P2P signaling 상태는 MySQL에 저장된다. 음성 자체는 WebRTC P2P로 기기 간에 직접 전달한다.

Android FCM은 Firebase Console 설정과 service-account credential이 준비된 환경에서 통화 신청·새
메시지를 발송한다. 오디오와 메시지 본문은 FCM payload에 넣지 않으며, 앱은 알림 이벤트 뒤 보호된
API를 다시 조회한다.

로컬 개발은 service-account key 대신 Google Cloud Application Default Credentials(ADC)를 사용할 수
있다. `gcloud auth application-default login` 뒤 `.env`에 `MOHANO_FCM_ENABLED=true`와
`MOHANO_FIREBASE_PROJECT_ID=mohano-512515`를 설정한다. 운영 환경에서는 key JSON보다 실행 환경에
부착된 service account 또는 Workload Identity를 우선한다.

### Apple 로그인 환경 변수

Apple 로그인은 앱이 전달한 ID token을 Apple 공개 키로 검증한 뒤 MOHANO JWT로 교환한다. `.env`에는
iOS Bundle ID와 Android/web Service ID를 모두 등록한다.

```dotenv
MOHANO_APPLE_CLIENT_IDS=com.example.mohano,com.example.mohano.web
MOHANO_APPLE_ANDROID_PACKAGE_ID=com.example.mohano
```

Android Apple 로그인은 외부 HTTPS callback URL을 필요로 한다. Apple Developer portal의 Return URL과
Flutter `MOHANO_APPLE_REDIRECT_URI`에는 같은 주소(예: `https://api.example.com/v1/auth/apple/callback`)를
등록한다. `POST /v1/auth/apple/callback`은 Android 앱으로 provider 결과를 되돌려 주며, 로그인 여부는
그 뒤 `POST /v1/auth/apple/exchange`의 Apple ID token 검증 결과로만 결정한다.

### LINE 로그인 환경 변수

LINE native SDK가 보낸 ID token은 `POST /v1/auth/line/exchange`로 전달된다. 서버는
`https://api.line.me/oauth2/v2.1/verify`에서 Channel ID와 nonce를 포함해 검증한 뒤, 검증 응답의
`sub`만 identity 키로 사용한다. Channel secret은 이 흐름에 사용하지 않는다.

```dotenv
MOHANO_LINE_CHANNEL_ID=1234567890
```

### Kakao 로그인 환경 변수

Kakao native SDK가 발급한 access token은 `POST /v1/auth/kakao/exchange`로 전달된다. 서버는
Kakao의 token-info API에서 토큰 유효성과 발급 앱 ID를 직접 확인한 뒤, 검증된 Kakao 사용자 ID만
identity 키로 사용한다. REST API key나 Admin key는 이 로그인 검증에 사용하지 않는다.

```dotenv
# Kakao Developers > My Application > App settings > App ID
MOHANO_KAKAO_APP_ID=123456
```

## 실행 준비

### 로컬 인프라 컨테이너

`etc/infra`에는 로컬 전용 MySQL과 Silo(MinIO 호환)가 함께 준비된다. 별도 infra `.env` 파일 없이
`etc/infra`에서 다음을 실행한다.

    docker compose up -d --build

MySQL은 기본적으로 `127.0.0.1:3306`에만 열리며, FastAPI는 로컬 Python 프로세스로
실행한다. Silo S3 API는 `http://127.0.0.1:9000`, 관리 콘솔은
`http://127.0.0.1:9001`에만 열린다. Compose 기동 뒤 `minio-init` 작업이 성공 종료하면
비공개 `mohano-profile-images` 버킷을 사용할 수 있다.

Silo는 MinIO 호환 로컬 사진 저장소다. FastAPI는 짧게 만료되는 signed PUT/GET URL만 발급하고,
앱은 장기 storage 자격 증명 없이 사진을 직접 업로드·조회한다. 운영에서는 같은 S3 호환 계약을
Cloudflare R2로 전환한다.

### GCP 운영 배포

운영 환경은 **Cloud Run(FastAPI 컨테이너) + Cloud SQL for MySQL + Cloudflare R2**를 사용한다.
Cloud Run이 HTTPS와 컨테이너 실행을 담당하므로 Caddy나 공개 VM은 사용하지 않는다. Cloud SQL과
Cloud Run은 Unix socket/Cloud SQL connector로만 통신하며, R2 자격 증명은 Secret Manager 참조로
주입한다. 개발 환경은 운영자 요청에 따라 DB URL·JWT·Swagger Basic Auth 값을 Cloud Run 리비전 설정에
표시할 수 있으므로, 해당 환경의 Terraform state와 Cloud Run 설정 접근 권한을 제한한다. Terraform 분리
스택, Secret Manager 등록, 이미지 빌드, migration job 실행 순서는
[GCP 운영 인프라 안내](etc/infra/gcp/README.md)를 따른다.

### FastAPI

사용 중인 Python으로 가상 환경을 만들고 의존성을 설치한다. 더미 API 단계에서는 MySQL을
실행하거나 migration을 적용할 필요가 없다. `.env.example`을 `.env`로 복사해 최소한
`MOHANO_JWT_SECRET_KEY`를 안전한 값으로 변경한다.

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    uvicorn app.main:app --reload

MySQL 전환 시에만 `alembic upgrade head`를 실행한다. 서버 실행과 migration은 사용자가
수행한다. 실제 OAuth provider secret과 JWT secret은 저장소에 추가하지 않는다.

### Flutter Web 로컬 연동

기본 CORS 설정은 `localhost`와 `127.0.0.1`의 로컬 포트만 허용한다. Flutter 앱은 별도 설정이
없으면 `http://127.0.0.1:8000/v1`을 사용한다. 다른 개발 서버 주소를 쓸 때만 Flutter 실행에
`--dart-define=MOHANO_API_BASE_URL=http://<host>:<port>/v1`을 추가한다.

### VS Code F5 실행

Python 확장을 설치한 뒤 `MOHANO-SERVER` 폴더를 VS Code 작업 폴더로 열고 F5를 누른다.
`.vscode/launch.json`의 `MOHANO Server (FastAPI)` 설정은 아래 명령과 같은 서버를 debug
mode로 기동한다.

    python -m uvicorn app.main:app --reload

## 설계 문서

서버 설계의 기준은 `etc/design/00-start.txt`와 기능별 문서다.
