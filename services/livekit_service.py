import time
from typing import Optional
from jose import jwt
from config import settings

class LiveKitService:
    @staticmethod
    def generate_token(
        room_name: str,
        participant_identity: str,
        participant_name: str,
        is_teacher: bool = False
    ) -> str:
        """
        Generates a secure LiveKit WebRTC Access Token.
        - Teacher: canPublish, canSubscribe, canPublishData, roomAdmin
        - Student: canPublish, canSubscribe, canPublishData (restricted to teacher video in client/server)
        """
        now = int(time.time())
        exp = now + (24 * 3600) # 24 hours validity

        # First attempt using official livekit.api if available
        try:
            from livekit import api
            grants = api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                room_admin=is_teacher,
            )
            token = (
                api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
                .with_identity(participant_identity)
                .with_name(participant_name)
                .with_grants(grants)
                .to_jwt()
            )
            return token
        except Exception:
            # Standard RFC-compliant LiveKit JWT generation
            payload = {
                "sub": participant_identity,
                "name": participant_name,
                "iss": settings.LIVEKIT_API_KEY,
                "nbf": now - 10,
                "exp": exp,
                "video": {
                    "roomJoin": True,
                    "room": room_name,
                    "canPublish": True,
                    "canSubscribe": True,
                    "canPublishData": True,
                    "roomAdmin": is_teacher
                },
                "metadata": '{"is_teacher": ' + ('true' if is_teacher else 'false') + '}'
            }
            return jwt.encode(payload, settings.LIVEKIT_API_SECRET, algorithm="HS256")
