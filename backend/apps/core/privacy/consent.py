"""
Face consent gate enforcement for face swap operations.
"""
import structlog
from typing import Dict, Any, Optional, List
from enum import Enum

logger = structlog.get_logger(__name__)


class ConsentRequirement(Enum):
    """Types of consent requirements."""
    FACE_SWAP_CONSENT = "face_swap_consent"
    DEEPFAKE_AWARENESS = "deepfake_awareness"
    BIOMETRIC_PROCESSING = "biometric_processing"


class FaceConsentService:
    """Service for enforcing face consent requirements for face swap operations."""
    
    def __init__(self):
        """Initialize face consent service with plan-based requirements."""
        # Plan-based consent requirements
        self.plan_requirements = {
            "free": {
                "required_consents": [
                    ConsentRequirement.FACE_SWAP_CONSENT,
                    ConsentRequirement.DEEPFAKE_AWARENESS
                ],
                "strict_enforcement": True,
                "commercial_use_allowed": False
            },
            "pro": {
                "required_consents": [
                    ConsentRequirement.FACE_SWAP_CONSENT,
                    ConsentRequirement.BIOMETRIC_PROCESSING
                ],
                "strict_enforcement": True,
                "commercial_use_allowed": True
            },
            "premium": {
                "required_consents": [
                    ConsentRequirement.FACE_SWAP_CONSENT
                ],
                "strict_enforcement": False,
                "commercial_use_allowed": True
            }
        }
    
    def validate_face_swap_consent(
        self, 
        job_params: Dict[str, Any], 
        user_plan: str,
        job_type: str
    ) -> Dict[str, Any]:
        """
        Validate face swap consent requirements for job creation.
        
        Args:
            job_params: Job parameters including consent flags
            user_plan: User's subscription plan
            job_type: Type of job being created
            
        Returns:
            Dictionary with consent validation results
        """
        validation_result = {
            "consent_valid": True,
            "violations": [],
            "warnings": [],
            "required_consents": [],
            "missing_consents": [],
            "plan": user_plan,
            "job_type": job_type
        }
        
        # Only apply to face swap jobs
        if job_type != "face_swap":
            validation_result["applicable"] = False
            return validation_result
        
        validation_result["applicable"] = True
        
        try:
            # Get plan requirements
            plan_config = self.plan_requirements.get(user_plan, self.plan_requirements["free"])
            required_consents = plan_config["required_consents"]
            strict_enforcement = plan_config["strict_enforcement"]
            
            validation_result["required_consents"] = [c.value for c in required_consents]
            validation_result["strict_enforcement"] = strict_enforcement
            
            # Check each required consent
            for consent_type in required_consents:
                consent_key = self._get_consent_param_key(consent_type)
                consent_given = job_params.get(consent_key, False)
                
                if not consent_given:
                    violation = {
                        "type": "missing_consent",
                        "consent_type": consent_type.value,
                        "message": self._get_consent_violation_message(consent_type),
                        "required_param": consent_key,
                        "enforcement": "strict" if strict_enforcement else "warning"
                    }
                    
                    if strict_enforcement:
                        validation_result["violations"].append(violation)
                        validation_result["consent_valid"] = False
                    else:
                        validation_result["warnings"].append(violation)
                    
                    validation_result["missing_consents"].append(consent_type.value)
            
            # Check commercial use permissions
            if not plan_config["commercial_use_allowed"]:
                commercial_intent = job_params.get("commercial_use", False)
                if commercial_intent:
                    validation_result["violations"].append({
                        "type": "plan_restriction",
                        "message": "Commercial use is not allowed on your current plan"
                    })
                    validation_result["consent_valid"] = False
            
            logger.info("Face consent validation completed",
                       job_type=job_type,
                       plan=user_plan,
                       consent_valid=validation_result["consent_valid"],
                       violations_count=len(validation_result["violations"]))
            
        except Exception as e:
            logger.error("Face consent validation failed", error=str(e))
            validation_result.update({
                "consent_valid": False,
                "error": str(e),
                "violations": [{"type": "validation_error", "message": "Consent validation system error"}]
            })
        
        return validation_result
    
    def _get_consent_param_key(self, consent_type: ConsentRequirement) -> str:
        """Get the parameter key name for a consent type."""
        consent_param_mapping = {
            ConsentRequirement.FACE_SWAP_CONSENT: "face_swap_consent",
            ConsentRequirement.DEEPFAKE_AWARENESS: "deepfake_awareness_consent",
            ConsentRequirement.BIOMETRIC_PROCESSING: "biometric_processing_consent"
        }
        return consent_param_mapping.get(consent_type, f"{consent_type.value}_consent")
    
    def _get_consent_violation_message(self, consent_type: ConsentRequirement) -> str:
        """Get user-friendly message for consent violation."""
        messages = {
            ConsentRequirement.FACE_SWAP_CONSENT: 
                "Face swap consent is required. You must acknowledge that you have permission to process the faces in these images.",
            ConsentRequirement.DEEPFAKE_AWARENESS: 
                "Deepfake awareness consent is required. You must acknowledge the potential for misuse and agree to ethical usage.",
            ConsentRequirement.BIOMETRIC_PROCESSING: 
                "Biometric processing consent is required. You must consent to facial feature analysis and processing."
        }
        return messages.get(consent_type, f"Consent required for {consent_type.value}")
    
    def get_required_consents_for_plan(self, user_plan: str) -> Dict[str, Any]:
        """
        Get list of required consents for a user plan.
        
        Args:
            user_plan: User's subscription plan
            
        Returns:
            Dictionary with consent requirements for the plan
        """
        plan_config = self.plan_requirements.get(user_plan, self.plan_requirements["free"])
        
        consent_details = []
        for consent_type in plan_config["required_consents"]:
            consent_details.append({
                "type": consent_type.value,
                "param_key": self._get_consent_param_key(consent_type),
                "description": self._get_consent_description(consent_type),
                "required": True
            })
        
        return {
            "plan": user_plan,
            "strict_enforcement": plan_config["strict_enforcement"],
            "commercial_use_allowed": plan_config["commercial_use_allowed"],
            "required_consents": consent_details
        }
    
    def _get_consent_description(self, consent_type: ConsentRequirement) -> str:
        """Get detailed description for consent type."""
        descriptions = {
            ConsentRequirement.FACE_SWAP_CONSENT: 
                "I confirm that I have explicit permission to process the faces shown in the uploaded images.",
            ConsentRequirement.DEEPFAKE_AWARENESS: 
                "I understand that this technology can create realistic but artificial images, and I agree to use it responsibly.",
            ConsentRequirement.BIOMETRIC_PROCESSING: 
                "I consent to the processing of facial biometric data for the purpose of face swapping."
        }
        return descriptions.get(consent_type, f"Consent required for {consent_type.value}")