"use client";

import type React from "react";
import {
  Bot,
  Book,
  Wrench,
  Network,
  MessageCircleMore,
  Users,
  Component,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useParams } from "next/navigation";
import { useI18n } from "@/hooks/useI18n";
import type { Locale } from "@/i18n";

export function CoreCapabilities() {
  const { lang } = useParams();
  const { t, ta } = useI18n(lang as Locale);

  const capabilities = [
    {
      icon: <Bot className="text-white" />,
      title: t("CoreCapabilities.cards.intelligentOrchestration.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.intelligentOrchestration.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <Book className="text-white" />,
      title: t("CoreCapabilities.cards.knowledgeManagement.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.knowledgeManagement.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <Wrench className="text-white" />,
      title: t("CoreCapabilities.cards.mcpToolIntegration.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.mcpToolIntegration.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <Network className="text-white" />,
      title: t("CoreCapabilities.cards.multiChannelAccess.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.multiChannelAccess.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <MessageCircleMore className="text-white" />,
      title: t("CoreCapabilities.cards.realTimeCommunication.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.realTimeCommunication.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <Users className="text-white" />,
      title: t("CoreCapabilities.cards.humanAgentCollaboration.title"),
      features: ta<string[]>(
        "CoreCapabilities.cards.humanAgentCollaboration.features",
      ),
      color: "from-blue-600 to-blue-400",
    },
    {
      icon: <Component className="text-white" />,
      title: t("CoreCapabilities.cards.uiWidgetSystem.title"),
      features: ta<string[]>("CoreCapabilities.cards.uiWidgetSystem.features"),
      color: "from-blue-600 to-blue-400",
    },
  ];
  return (
    <section
      id="capabilities"
      className="py-24 px-4 bg-linear-to-b from-transparent to-gray-50 dark:to-gray-900/30"
    >
      <div className="container mx-auto max-w-[1400px]">
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-4xl font-bold mb-6 bg-clip-text text-transparent bg-linear-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400">
            {t("CoreCapabilities.title")}
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-3xl mx-auto">
            {t("CoreCapabilities.description")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {capabilities.map((capability, index) => (
            <CapabilityCard key={index} {...capability} />
          ))}
        </div>
      </div>
    </section>
  );
}

function CapabilityCard({
  icon,
  title,
  features,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  features: string[];
  color: string;
}) {
  return (
    <div className="group bg-white dark:bg-gray-800/80 rounded-xl shadow-lg hover:shadow-xl duration-300 overflow-hidden border border-gray-100 dark:border-gray-700 backdrop-blur-sm">
      <div className={cn("h-2 bg-linear-to-r", color)}></div>
      <div className="p-8">
        <div className="flex items-center gap-4 mb-6">
          <div
            className={cn(
              "p-3 rounded-xl bg-linear-to-br shadow-sm",
              color,
              "duration-300",
            )}
          >
            {icon}
          </div>
          <h3 className="text-xl font-bold">{title}</h3>
        </div>
        <ul className="space-y-3">
          {features.map((feature, index) => (
            <li key={index} className="flex items-start gap-3">
              <span
                className={cn(
                  "inline-block w-2 h-2 rounded-full bg-linear-to-r mt-2",
                  color,
                )}
              ></span>
              <span className="text-gray-700 dark:text-gray-300">
                {feature}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
