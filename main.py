import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional

from loguru import logger
from pydantic import UUID4, BaseModel, Field, FilePath
from swarms import SequentialWorkflow, create_file_in_folder

from radiology_swarm.swarm_wrapper import agents, treatment_specialist


class ImageType(str, Enum):
    """Supported image types for radiology analysis"""

    XRAY = "xray"
    CT = "ct"
    MRI = "mri"
    ULTRASOUND = "ultrasound"
    PET = "pet"
    NUCLEAR = "nuclear"


class Priority(str, Enum):
    """Priority levels for analysis"""

    STAT = "stat"
    URGENT = "urgent"
    ROUTINE = "routine"


class AnalysisStatus(str, Enum):
    """Status of the analysis process"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageMetadata(BaseModel):
    """Metadata for medical images"""

    file_path: FilePath
    image_type: ImageType
    modality: str
    acquisition_date: Optional[datetime] = None
    dimensions: Optional[tuple[int, int]] = None
    file_size: Optional[int] = None
    original_format: str
    converted_format: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class PatientInfo(BaseModel):
    """Patient information schema"""

    patient_id: UUID4 = Field(default_factory=uuid.uuid4)
    medical_record_number: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Literal["M", "F", "O"]] = None
    clinical_history: Optional[str] = None

    class Config:
        frozen = True


class AnalysisRequest(BaseModel):
    """Schema for analysis request"""

    request_id: UUID4 = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    task: str = Field(..., min_length=10)
    image_path: FilePath
    priority: Priority = Field(default=Priority.ROUTINE)
    patient_info: Optional[PatientInfo] = None
    additional_context: Optional[Dict[str, str]] = None
    output_preferences: Optional[Dict[str, str]] = None

    class Config:
        arbitrary_types_allowed = True


class TreatmentPlan(BaseModel):
    """Treatment plan details"""

    plan_id: UUID4 = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recommendations: List[str]
    priority: Priority
    follow_up_required: bool
    follow_up_timeline: Optional[str] = None
    contraindications: Optional[List[str]] = None
    alternative_options: Optional[List[str]] = None


class AnalysisOutput(BaseModel):
    """Complete analysis output schema"""

    analysis_id: UUID4 = Field(default_factory=uuid.uuid4)
    request: AnalysisRequest
    status: AnalysisStatus
    start_time: datetime
    end_time: datetime
    processing_duration: float
    image_metadata: ImageMetadata
    diagnosis_results: str
    treatment_plan: TreatmentPlan
    output_files: Dict[str, Path]
    error_log: Optional[List[str]] = None

    class Config:
        arbitrary_types_allowed = True

    def to_report(self) -> str:
        """Convert analysis output to markdown report"""
        # Implementation for report generation
        pass


def run_diagnosis_agents(
    task: str,
    img: str,
    output_folder_name: str = "reports",
    output_file_name: str = "xray_analysis.md",
    patient_info: Optional[PatientInfo] = None,
    priority: Priority = Priority.ROUTINE,
) -> AnalysisOutput:
    """
    Run diagnosis agents with structured input/output

    Args:
        task: Analysis task description
        img: Path to image file
        output_folder_name: Output folder name
        output_file_name: Output file name
        patient_info: Optional patient information
        priority: Analysis priority level

    Returns:
        AnalysisOutput object containing complete analysis results
    """
    try:
        start_time = datetime.utcnow()

        # Create analysis request
        request = AnalysisRequest(
            task=task,
            image_path=Path(img),
            priority=priority,
            patient_info=patient_info,
        )

        # # Convert image if needed
        # if not img.lower().endswith((".jpg", ".jpeg")):
        #     converter = MedicalImageConverter(output_dir="temp_converted")
        #     img = converter.convert_to_jpeg(img)
        #     logger.info(f"Converted image to JPEG: {img}")

        # Get image metadata
        image_metadata = ImageMetadata(
            file_path=Path(img),
            image_type=ImageType.XRAY,  # Default to XRAY, should be determined from DICOM
            modality="XR",
            original_format=Path(img).suffix,
            converted_format=".jpg" if img.endswith(".jpg") else None,
        )

        # Run analysis workflow
        radiology_swarm = SequentialWorkflow(
            name="radiology-swarm",
            description="swarm of autonomous radiologist agents",
            agents=agents,
        )

        diagnosis = radiology_swarm.run(task=task, img=img)

        # Generate treatment plan
        treatment_output = treatment_specialist.run(
            f"From diagnosis swarm: {str(diagnosis)} \n Your Task is: {task}"
        )

        treatment_plan = TreatmentPlan(
            recommendations=[treatment_output],
            priority=priority,
            follow_up_required=True,  # Should be determined from analysis
        )

        # Create output files
        output_path = create_file_in_folder(
            output_folder_name, output_file_name, treatment_output
        )

        # Construct final output
        analysis_output = AnalysisOutput(
            request=request,
            status=AnalysisStatus.COMPLETED,
            start_time=start_time,
            end_time=datetime.utcnow(),
            processing_duration=(
                datetime.utcnow() - start_time
            ).total_seconds(),
            image_metadata=image_metadata,
            diagnosis_results=diagnosis,
            treatment_plan=treatment_plan,
            output_files={"report": Path(output_path)},
        )

        return analysis_output.model_dump_json(indent=4)

    except Exception as e:
        logger.error(f"Error in diagnosis pipeline: {str(e)}")
        raise
