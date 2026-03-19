import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict

#schema
#Error report structure
class ComplianceIssue(TypedDict):
    category : str
    description : str
    severity : str
    timestamp : Optional[str]
    
    
#global graph state
class VideoAuditState(TypedDict):
    """
    Defines the data schema for lang graph execution
    """
    
    video_url : str
    video_id : str
    
    
    #ingestion and extraction data
    local_file_path : Optional[str]
    video_metadata : Dict[str,Any]
    transcript : Optional[str]
    oct_text : List[str]
    
    #analysis output
    compliance_results : Annotated[List[ComplianceIssue], operator.add]
    
    # final deliverable
    final_status : str 
    final_report : str
    
    #system observability
    errors : Annotated[List[str], operator.add]