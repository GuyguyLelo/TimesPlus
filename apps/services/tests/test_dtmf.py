from django.test import TestCase

from apps.agents.models import Agent
from apps.services.dgtcp import assurer_agents_dtmf
from apps.services.models import Service


class AgentsDtmfTests(TestCase):
    def test_ten_agents_belong_to_the_treasury_direction(self):
        assurer_agents_dtmf()
        direction = Service.objects.get(code="DTMF")
        agents = Agent.objects.filter(matricule__startswith="DTMF-").select_related(
            "service",
            "service__service_parent",
            "service__service_parent__service_parent",
        )
        self.assertEqual(agents.count(), 10)
        for agent in agents:
            filiation = {unite.code for unite in agent.service.filiation()}
            self.assertIn(direction.code, filiation)
        self.assertEqual(Agent.objects.filter(service=direction).count(), 1)
        self.assertEqual(Agent.objects.filter(service__code="DTMF-TRES").count(), 1)
        self.assertEqual(Agent.objects.filter(service__code="DTMF-FIN-HOR").count(), 1)
