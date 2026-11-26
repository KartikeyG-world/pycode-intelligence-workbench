import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.analyzers.ast_parser import SafeASTParser
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    CodeStatistics,
    CodeStructureData,
    TheoreticalGraphData,
)
from app.models.models import CodeSubmission, AnalysisResult

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.parser = SafeASTParser()
        self.analyzer = ComplexityAnalyzer()

    def analyze_code(
        self, request: AnalyzeRequest, db: Optional[Session] = None
    ) -> AnalyzeResponse:
        # 1. Parse AST
        tree, syntax_error = self.parser.parse_code(request.code)

        if syntax_error is not None:
            return AnalyzeResponse(
                success=False,
                time_complexity="N/A",
                space_complexity="N/A",
                confidence="LOW",
                complexity_reasoning=f"Code could not be analyzed due to a syntax error on line {syntax_error.line}: {syntax_error.message}",
                statistics=CodeStatistics(),
                detected_patterns=["Syntax Error"],
                optimization_suggestions=[],
                structure=CodeStructureData(),
                graph=TheoreticalGraphData(active_complexity="O(1)", growth_points=[]),
                error=syntax_error,
            )

        # 2. Perform static analysis
        response = self.analyzer.analyze(tree)

        # 3. Optional persistence to Database
        if db is None:
            response.persistence_status = "skipped"
            return response

        try:
            submission = CodeSubmission(
                project_id=request.project_id,
                title=request.title or "Untitled Snippet",
                code=request.code,
            )
            db.add(submission)
            db.flush()

            result_record = AnalysisResult(
                submission_id=submission.id,
                time_complexity=response.time_complexity,
                space_complexity=response.space_complexity,
                confidence=response.confidence,
                complexity_reasoning=response.complexity_reasoning,
                statistics=response.statistics.model_dump(),
                structure=response.structure.model_dump(),
                graph_data=response.graph.model_dump(),
                detected_patterns=response.detected_patterns,
                optimization_suggestions=response.optimization_suggestions,
            )
            db.add(result_record)
            db.commit()
            response.submission_id = submission.id
            response.persistence_status = "saved"
            response.persistence_warning = None
        except Exception:
            db.rollback()
            logger.exception("Failed to persist analysis result to database")
            response.submission_id = None
            response.persistence_status = "failed"
            response.persistence_warning = (
                "Analysis succeeded, but saving to history failed. "
                "This result will not appear in your analysis history."
            )

        return response
