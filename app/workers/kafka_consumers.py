import json
import logging
import asyncio
from kafka import KafkaConsumer
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.ml.sif_nlp import sif_engine

logger = logging.getLogger(__name__)

class AutomatedSIFScorer:
    def __init__(self):
        self.is_running = False
        
        # We mock the consumer for local environments if Kafka isn't running
        self.use_mock = True 

    def process_incident(self, incident_data: dict):
        """Passes the incident to the SIF NLP engine and saves results."""
        narrative = incident_data.get("narrative", "")
        if not narrative:
            return
            
        logger.info(f"Processing incident for SIF: {incident_data.get('id')}")
        result = sif_engine.detect_sif_precursors(narrative)
        
        # In production, this would save to a `SIFDetection` table
        if result["is_sif_precursor"]:
            logger.warning(f"🚨 SIF Precursor Detected! Category: {result['top_category']}")
            
    async def start_consumer(self):
        self.is_running = True
        logger.info("Started Kafka Consumer for Automated SIF Scoring")
        
        if self.use_mock:
            # Mock listening loop for testing architecture
            while self.is_running:
                await asyncio.sleep(60)
        else:
            # Real Kafka Consumer
            consumer = KafkaConsumer(
                'hse.incident.validated',
                bootstrap_servers=['localhost:9092'],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='sif-scoring-group',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            
            for message in consumer:
                if not self.is_running:
                    break
                incident = message.value
                self.process_incident(incident)

    def stop_consumer(self):
        self.is_running = False
        logger.info("Stopped Kafka Consumer")

# Global singleton
sif_scorer_worker = AutomatedSIFScorer()
